"""Private owner-scoped SDK verification job service for Forge Studio.

Not a public MCP endpoint. Binds localhost by default; only a trusted HTTPS
proxy or tunnel with network-level restrictions can expose it to Sites. No
secrets, user-supplied code, or project source enter logs.

The Sites adapter authenticates the viewer and signs every request with the
server-side FORGE_SDK_BRIDGE_SECRET. A model-supplied user id is never trusted.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time

REPO = Path(__file__).resolve().parents[1]
VERIFY = REPO / "ci" / "verify_studio_archive.py"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MAX_BODY = 1_550_000
MAX_ZIP = 1_000_000
TIME_WINDOW = 90
FINAL = {"PASS", "FAIL", "REJECTED", "TIMEOUT", "INTERRUPTED"}


def encode_json(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def verify_signature(key: str, timestamp: str, path: str, raw: bytes, signature: str, now: float | None = None) -> bool:
    if not timestamp.isdecimal() or len(timestamp) > 15 or not re.fullmatch(r"[0-9a-f]{64}", signature):
        return False
    current = time.time() if now is None else now
    if abs(current - int(timestamp)) > TIME_WINDOW:
        return False
    expected = hmac.new(key.encode("utf-8"), timestamp.encode() + b"\n" +
                        path.encode("ascii") + b"\n" + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class JobStore:
    def __init__(self, workspace: str, secret: str, verifier=VERIFY):
        root = Path(workspace)
        if not root.is_absolute() or root.is_symlink() or len(secret) < 32:
            raise ValueError("Private absolute workspace and strong secret required")
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Workspace is not a directory")
        self.secret = secret
        self.verifier = Path(verifier).resolve(strict=True)
        self.lock = threading.RLock()
        self.active = 0
        self.capacity = 2

    def job_directory(self, subject: str, job_id: str) -> Path:
        if not SHA_RE.fullmatch(subject) or not SHA_RE.fullmatch(job_id):
            raise ValueError("Invalid identity or job ID")
        root = self.root / "sdk-jobs"
        root.mkdir(mode=0o700, exist_ok=True)
        owner = root / subject
        if owner.is_symlink():
            raise ValueError("Unsafe workspace identity")
        owner.mkdir(mode=0o700, exist_ok=True)
        target = owner / job_id
        if target.is_symlink():
            raise ValueError("Unsafe job")
        return target

    def meta(self, subject: str, job_id: str):
        folder = self.job_directory(subject, job_id)
        meta = folder / "status.json"
        if not meta.is_file() or meta.is_symlink():
            return None
        return json.loads(meta.read_text("utf-8"))

    def write_meta(self, subject: str, job_id: str, payload: dict):
        folder = self.job_directory(subject, job_id)
        folder.mkdir(mode=0o700, exist_ok=True)
        path = folder / "status.json"
        temp = folder / ("." + str(threading.get_ident()) + ".tmp")
        temp.write_bytes(encode_json(payload))
        temp.replace(path)

    def start(self, value: object) -> tuple[int, dict]:
        if not isinstance(value, dict) or set(value) != {"subject_hash", "project_id", "sha256", "zip_base64"}:
            raise ValueError("Invalid request schema")
        subject, project, sha = value["subject_hash"], value["project_id"], value["sha256"]
        if not all(isinstance(v, str) for v in (subject, project, sha)) or not SHA_RE.fullmatch(subject) or not SHA_RE.fullmatch(sha) or not UUID_RE.fullmatch(project):
            raise ValueError("Invalid job scope or artifact hash")
        encoded = value["zip_base64"]
        if not isinstance(encoded, str) or len(encoded) > 1_350_000:
            raise ValueError("Oversized artifact")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise ValueError("Invalid ZIP encoding") from exc
        if not data or len(data) > MAX_ZIP or hashlib.sha256(data).hexdigest() != sha:
            raise ValueError("Artifact exceeds limit or does not match SHA-256")

        # Content-addressed jobs make retry safe. No new execution for
        # identical user/project/export.
        job_id = hashlib.sha256((subject + ":" + project + ":" + sha).encode()).hexdigest()
        with self.lock:
            old = self.meta(subject, job_id)
            if old:
                return 200, self.public_state(old)
            if self.active >= self.capacity:
                return 429, {"error": "Job capacity reached"}
            directory = self.job_directory(subject, job_id)
            directory.mkdir(mode=0o700, exist_ok=False)
            (directory / "export.zip").write_bytes(data)
            meta = {"job_id": job_id, "project_id": project, "sha256": sha,
                    "status": "QUEUED", "created_at": int(time.time())}
            self.write_meta(subject, job_id, meta)
            self.active += 1
            self._running_ids = getattr(self, "_running_ids", set())
            self._running_ids.add(job_id)
            threading.Thread(target=self._execute, args=(subject, job_id),
                             daemon=True, name="forge-sdk-job").start()
        return 202, self.public_state(meta)

    def status(self, value: object) -> dict:
        if not isinstance(value, dict) or set(value) != {"subject_hash", "project_id", "job_id"}:
            raise ValueError("Invalid status request")
        subject, project, jid = value["subject_hash"], value["project_id"], value["job_id"]
        if not isinstance(subject, str) or not isinstance(jid, str) or not isinstance(project, str) or not SHA_RE.fullmatch(subject) or not SHA_RE.fullmatch(jid) or not UUID_RE.fullmatch(project):
            raise ValueError("Invalid job scope")
        with self.lock:
            meta = self.meta(subject, jid)
        if not meta or meta.get("project_id") != project:
            raise FileNotFoundError("Job not found")
        # Detect interrupted jobs after host restart. Never call this PASS.
        if meta["status"] in ("QUEUED", "RUNNING") and jid not in self.live_jobs:
            meta = {**meta, "status": "INTERRUPTED"}
        return self.public_state(meta)

    @property
    def live_jobs(self):
        return getattr(self, "_running_ids", set())

    @staticmethod
    def public_state(meta: dict) -> dict:
        response = {key: meta[key] for key in
                    ("job_id", "project_id", "sha256", "status", "created_at", "finished_at")
                    if key in meta}
        if meta.get("status") in FINAL:
            response["verification"] = meta.get("verification", {
                "passed": False, "official_sdk": "UNKNOWN"
            })
        return response

    def _execute(self, subject: str, jid: str):
        directory = self.job_directory(subject, jid)
        try:
            with self.lock:
                self._running_ids = getattr(self, "_running_ids", set())
                self._running_ids.add(jid)
                meta = self.meta(subject, jid)
                self.write_meta(subject, jid, {**meta, "status": "RUNNING"})
            environment = {
                "PATH": os.environ.get("PATH", "/usr/bin"),
                "HOME": str(directory),
                "LANG": "C.UTF-8",
                "PYTHONDONTWRITEBYTECODE": "1",
                "ALDOL_API_BASE_URL": "",
                "ALDOL_API_ALLOWED_HOST": "",
            }
            try:
                proc = subprocess.run(
                    [sys.executable, "-B", str(self.verifier), str(directory / "export.zip")],
                    capture_output=True, text=True, timeout=95, env=environment,
                    cwd=REPO, check=False,
                )
                report = json.loads(proc.stdout.strip())
                passed = (proc.returncode == 0 and report.get("passed") is True
                          and report.get("official_sdk") == "PASS"
                          and report.get("inmemory") == "PASS"
                          and report.get("stdio") == "PASS"
                          and report.get("network_used") is False)
                verification = {key: report[key] for key in (
                    "passed", "official_sdk", "sdk_version", "inmemory", "stdio",
                    "network_used", "files_checked", "kind", "version",
                ) if key in report}
                if not passed:
                    verification = {"passed": False, "official_sdk": "FAIL"}
                final = "PASS" if passed else "FAIL"
            except (subprocess.TimeoutExpired, ValueError, OSError, json.JSONDecodeError):
                final, verification = "TIMEOUT", {"passed": False, "official_sdk": "UNKNOWN"}
            with self.lock:
                meta = self.meta(subject, jid)
                self.write_meta(subject, jid, {
                    **meta, "status": final, "verification": verification,
                    "finished_at": int(time.time()),
                })
        except Exception:
            # Fail closed even if the verifier crashes unexpectedly. Never leave
            # a stale RUNNING/PASS status, and never log extracted source.
            with self.lock:
                meta = self.meta(subject, jid)
                if meta:
                    self.write_meta(subject, jid, {
                        **meta, "status": "FAIL",
                        "verification": {"passed": False, "official_sdk": "FAIL"},
                        "finished_at": int(time.time()),
                    })
        finally:
            (directory / "export.zip").unlink(missing_ok=True)
            with self.lock:
                getattr(self, "_running_ids", set()).discard(jid)
                self.active -= 1


def make_handler(store: JobStore):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ForgeSDKJobs/0.1"
        sys_version = ""

        def log_message(self, fmt, *args):
            return

        def send_json(self, status, obj):
            data = encode_json(obj)
            self.send_response(status)
            for name, value in {
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": str(len(data)),
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            }.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            path = self.path
            if path not in ("/v1/sdk/jobs", "/v1/sdk/jobs/status"):
                self.send_json(404, {"error": "Not found"})
                return
            count = self.headers.get("Content-Length", "")
            if not count.isdecimal() or not 0 < int(count) <= MAX_BODY:
                self.send_json(413, {"error": "Body size invalid"})
                return
            if self.headers.get("Origin") or not self.headers.get("Content-Type", "").startswith("application/json"):
                self.send_json(403, {"error": "Only trusted server-to-server JSON accepted"})
                return
            raw = self.rfile.read(int(count))
            timestamp = self.headers.get("X-Forge-Timestamp", "")
            signature = self.headers.get("X-Forge-Signature", "")
            if not verify_signature(store.secret, timestamp, path, raw, signature):
                self.send_json(401, {"error": "Unauthorized"})
                return
            try:
                value = json.loads(raw)
                if path == "/v1/sdk/jobs":
                    code, result = store.start(value)
                    self.send_json(code, result)
                else:
                    self.send_json(200, store.status(value))
            except FileNotFoundError:
                self.send_json(404, {"error": "Not found"})
            except (ValueError, TypeError, json.JSONDecodeError):
                self.send_json(400, {"error": "Request rejected"})

    return Handler


def main():
    secret = os.environ.get("FORGE_SDK_BRIDGE_SECRET", "")
    workspace = os.environ.get("FORGE_SDK_WORKSPACE_ROOT", "")
    if not workspace or not secret:
        raise SystemExit("SDK job service requires private workspace and secret")
    server = ThreadingHTTPServer(("127.0.0.1", 8775), make_handler(JobStore(workspace, secret)))
    server.serve_forever()


if __name__ == "__main__":
    main()
