"""Bounded MCP service over the preserved v0.3 CLI. No URL ingestion."""

from __future__ import annotations
import base64
import binascii
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile

MAX_UPLOAD = 2 * 1024 * 1024
MAX_EXPANDED = 8 * 1024 * 1024
MAX_ENTRIES = 100
MAX_REPORTS = 128
TTL = 86400
WORKER = Path(__file__).with_name("worker.py")


def status(checks):
    values = {c["status"] for c in checks}
    return (
        "FAIL"
        if "FAIL" in values
        else "UNKNOWN"
        if not values or "UNKNOWN" in values
        else "PASS"
    )


def safe_name(name):
    return (
        isinstance(name, str)
        and bool(name)
        and len(name) < 240
        and "\\" not in name
        and "\x00" not in name
        and not PurePosixPath(name).is_absolute()
        and not PureWindowsPath(name).drive
        and all(x not in ("", "..", ".") for x in name.rstrip("/").split("/"))
    )


class QAService:
    def __init__(self, artifact_root, report_root, remote=False, allow_browser=False):
        self.artifact_root = Path(artifact_root).resolve()
        self.report_root = Path(report_root).resolve()
        self.report_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.remote = remote
        self.allow_browser = allow_browser and not remote
        self.lock = threading.Lock()

    def _read(self, artifact):
        if not isinstance(artifact, dict) or artifact.keys() - {
            "filename",
            "content_base64",
            "path",
            "expected_sha256",
        }:
            raise ValueError("Invalid artifact fields")
        name = artifact.get("filename")
        if (
            not safe_name(name)
            or "/" in name
            or Path(name).suffix.lower() not in (".html", ".htm", ".zip")
        ):
            raise ValueError("filename must be a plain HTML/ZIP filename")
        if ("path" in artifact) == ("content_base64" in artifact):
            raise ValueError("Supply exactly one of path or content_base64")
        if "path" in artifact:
            if self.remote:
                raise ValueError("Host paths are disabled over HTTP")
            path = artifact["path"]
            if not safe_name(path):
                raise ValueError("Invalid local relative path")
            resolved = (self.artifact_root / path).resolve()
            if (
                not resolved.is_relative_to(self.artifact_root)
                or not resolved.is_file()
            ):
                raise ValueError("Artifact must be a file inside artifact root")
            if resolved.suffix.lower() != Path(name).suffix.lower():
                raise ValueError("Filename extension mismatch")
            with resolved.open("rb") as f:
                data = f.read(MAX_UPLOAD + 1)
        else:
            value = artifact["content_base64"]
            if not isinstance(value, str) or len(value) > 4 * ((MAX_UPLOAD + 2) // 3):
                raise ValueError("Upload limit exceeded")
            try:
                data = base64.b64decode(value, validate=True)
            except (ValueError, binascii.Error):
                raise ValueError("Invalid base64") from None
        if not data or len(data) > MAX_UPLOAD:
            raise ValueError("Upload must be 1 byte to 2 MiB")
        sha = hashlib.sha256(data).hexdigest()
        expected = artifact.get("expected_sha256")
        if expected is not None and (
            not isinstance(expected, str)
            or not re.fullmatch("[0-9a-fA-F]{64}", expected)
            or sha != expected.lower()
        ):
            raise ValueError("SHA-256 verification failed")
        files = {name: data}
        entry = name
        if name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    infos = z.infolist()
                    if len(infos) > MAX_ENTRIES:
                        raise ValueError("ZIP entry limit exceeded")
                    total = 0
                    files = {}
                    seen = set()
                    for info in infos:
                        n = info.filename
                        if not safe_name(n) or n.rstrip("/") in seen:
                            raise ValueError("Unsafe or duplicate ZIP path")
                        seen.add(n.rstrip("/"))
                        kind = (info.external_attr >> 16) & 0o170000
                        if kind not in (0, 0o100000, 0o040000):
                            raise ValueError("ZIP special files prohibited")
                        if info.flag_bits & 1:
                            raise ValueError("Encrypted ZIP prohibited")
                        total += info.file_size
                        if (
                            total > MAX_EXPANDED
                            or info.file_size > MAX_UPLOAD
                            or info.file_size > max(1024, info.compress_size) * 200
                        ):
                            raise ValueError("ZIP expansion limit exceeded")
                        if not info.is_dir():
                            files[n] = z.read(info)
                    htmls = sorted(
                        (x for x in files if x.lower().endswith((".html", ".htm"))),
                        key=lambda x: (
                            PurePosixPath(x).name.lower()
                            not in ("index.html", "index.htm"),
                            x.count("/"),
                            x,
                        ),
                    )
                    if not htmls:
                        raise ValueError("ZIP has no HTML entry")
                    entry = htmls[0]
            except (
                zipfile.BadZipFile,
                RuntimeError,
                NotImplementedError,
                EOFError,
            ) as exc:
                raise ValueError("Invalid or unsupported ZIP") from exc
        return data, {
            "filename": name,
            "sha256": sha,
            "entry": entry,
            "files_count": len(files),
            "bytes": len(data),
            "files": [
                {"name": n, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
                for n, b in files.items()
            ],
        }

    def _save(self, report):
        now = time.time()
        reports = sorted(
            self.report_root.glob("*.json"), key=lambda p: p.stat().st_mtime
        )
        for p in reports:
            if p.stat().st_mtime < now - TTL:
                p.unlink(missing_ok=True)
        reports = sorted(
            self.report_root.glob("*.json"), key=lambda p: p.stat().st_mtime
        )
        for p in reports[: max(0, len(reports) - MAX_REPORTS + 1)]:
            p.unlink(missing_ok=True)
        report.update(
            qa_id=uuid.uuid4().hex,
            version="0.4.0",
            created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        )
        target = self.report_root / (report["qa_id"] + ".json")
        text = json.dumps(report, ensure_ascii=False, indent=2)
        if len(text.encode()) > 2 * 1024 * 1024:
            raise ValueError("Report limit exceeded")
        target.write_text(text, encoding="utf-8")
        target.chmod(0o600)
        return report

    def get_qa_report(self, qa_id):
        if not isinstance(qa_id, str) or not re.fullmatch("[a-f0-9]{32}", qa_id):
            raise ValueError("Invalid QA ID")
        p = self.report_root / (qa_id + ".json")
        if not p.is_file() or p.stat().st_mtime < time.time() - TTL:
            raise ValueError("Report unavailable or expired")
        return json.loads(p.read_text(encoding="utf-8"))

    def inspect_game_artifact(self, artifact):
        with self.lock:
            _, meta = self._read(artifact)
            return self._save(
                {
                    "kind": "inspect",
                    "status": "PASS",
                    "artifact": meta,
                    "checks": [
                        {
                            "id": "artifact.integrity",
                            "status": "PASS",
                            "detail": "Bounded ingestion and SHA-256 computed; not a safety verdict",
                        }
                    ],
                    "coverage": {"browser": "UNKNOWN", "static": "UNKNOWN"},
                }
            )

    def _profile(self, profile):
        if profile is None:
            return {}
        if not isinstance(profile, dict) or len(json.dumps(profile)) > 64000:
            raise ValueError("Invalid profile")
        if profile.keys() - {
            "viewports",
            "responsive_tabs",
            "touch_targets",
            "scenarios",
            "screenshots",
        }:
            raise ValueError("Unknown profile field")
        for key in ("viewports", "responsive_tabs", "touch_targets", "scenarios"):
            if key in profile and (
                not isinstance(profile[key], list) or len(profile[key]) > 12
            ):
                raise ValueError("Invalid profile list")
        for vp in profile.get("viewports", []):
            if vp not in ("mobile320", "mobile360", "mobile390", "desktop"):
                raise ValueError("Unknown viewport")
        ids = []
        for s in profile.get("scenarios", []):
            if not isinstance(s, dict) or not re.fullmatch(
                "[A-Za-z0-9_-]{1,48}", s.get("id", "")
            ):
                raise ValueError("Invalid scenario ID")
            ids.append(s["id"])
            if not isinstance(s.get("steps"), list) or not 1 <= len(s["steps"]) <= 40:
                raise ValueError("Invalid scenario steps")
            for step in s["steps"]:
                if not isinstance(step, dict) or step.get("action") not in (
                    "click",
                    "tap",
                    "fill",
                    "select",
                    "wait",
                    "assert_count",
                    "assert_text",
                    "assert_visible",
                    "assert_state",
                    "assert_storage_key",
                    "reload_simulated",
                ):
                    raise ValueError("Unsupported scenario action")
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate scenario ID")
        for key in ("responsive_tabs", "touch_targets"):
            for x in profile.get(key, []):
                if (
                    not isinstance(x, dict)
                    or not re.fullmatch("[A-Za-z0-9_-]{1,48}", x.get("id", ""))
                    or not isinstance(x.get("selector"), str)
                ):
                    raise ValueError("Invalid responsive target")
        # Screenshots are scratch evidence, not unbounded persisted report data.
        return {**profile, "screenshots": False}

    def _run(self, artifact, kind, profile=None):
        with self.lock:
            data, meta = self._read(artifact)
            profile = self._profile(profile)
            checks = []
            blocked = kind != "static" and not self.allow_browser
            fingerprint = hashlib.sha256(
                json.dumps(profile, sort_keys=True).encode()
            ).hexdigest()
            if blocked:
                checks = [
                    {
                        "id": "browser.policy",
                        "status": "UNKNOWN",
                        "detail": "BLOCKED: browser execution is disabled; HTTP never runs artifact HTML",
                    }
                ]
            else:
                with tempfile.TemporaryDirectory(prefix="gameops-") as tmp:
                    root = Path(tmp)
                    target = root / meta["filename"]
                    target.write_bytes(data)
                    (root / "profile.json").write_text(
                        json.dumps(profile), encoding="utf-8"
                    )
                    env = {
                        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                        "HOME": str(root),
                        "LANG": "C.UTF-8",
                        "PYTHONDONTWRITEBYTECODE": "1",
                    }
                    if os.environ.get("ALDOL_CHROMIUM"):
                        env["ALDOL_CHROMIUM"] = os.environ["ALDOL_CHROMIUM"]
                    cmd = [
                        sys.executable,
                        str(WORKER),
                        str(target),
                        kind,
                        str(root / "profile.json"),
                        str(root),
                    ]
                    proc = subprocess.Popen(
                        cmd,
                        env=env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    try:
                        proc.wait(timeout=30 if kind == "static" else 90)
                        output = root / "result.json"
                        if (
                            proc.returncode
                            or not output.is_file()
                            or output.stat().st_size > 1024 * 1024
                        ):
                            raise RuntimeError("worker_failed")
                        checks = json.loads(output.read_text())
                    except (
                        subprocess.TimeoutExpired,
                        RuntimeError,
                        json.JSONDecodeError,
                    ):
                        checks = [
                            {
                                "id": "execution.worker",
                                "status": "UNKNOWN",
                                "detail": "Worker failed, exceeded limits or timed out",
                            }
                        ]
                    finally:
                        # Also terminate any descendants (Node/Chromium) after success or timeout.
                        if os.name == "posix":
                            try:
                                os.killpg(proc.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                        elif proc.poll() is None:
                            proc.kill()
                        proc.wait()
            return self._save(
                {
                    "kind": kind,
                    "status": status(checks),
                    "artifact": meta,
                    "profile_sha256": fingerprint,
                    "checks": checks,
                    "blocked": blocked,
                    "summary": {
                        s: sum(c["status"] == s for c in checks)
                        for s in ("PASS", "FAIL", "UNKNOWN")
                    },
                    "coverage": {
                        "static": "PASS" if kind == "static" else "UNKNOWN",
                        "browser": "UNKNOWN"
                        if kind == "static" or blocked
                        else status(checks),
                        "real_device": "UNKNOWN",
                    },
                    "environment": {
                        "transport": "http" if self.remote else "stdio",
                        "browser_method": "set_content + emulated localStorage",
                        "os_isolation_verified": False,
                    },
                }
            )

    def run_static_qa(self, artifact):
        return self._run(artifact, "static")

    def run_browser_qa(self, artifact, profile=None):
        return self._run(artifact, "browser", profile)

    def run_game_scenarios(self, artifact, profile):
        return self._run(artifact, "scenarios", profile)

    def compare_game_versions(self, baseline_id, candidate_id):
        with self.lock:
            base = self.get_qa_report(baseline_id)
            candidate = self.get_qa_report(candidate_id)
            b = {x["id"]: x for x in base["checks"]}
            c = {x["id"]: x for x in candidate["checks"]}
            regressions = [
                {"id": k, "before": b[k]["status"], "after": c[k]["status"]}
                for k in sorted(b.keys() & c.keys())
                if b[k]["status"] == "PASS" and c[k]["status"] == "FAIL"
            ]
            missing = sorted(b.keys() - c.keys())
            compatible = (
                base["kind"] == candidate["kind"]
                and base.get("profile_sha256") == candidate.get("profile_sha256")
                and base["kind"] in ("static", "browser", "scenarios")
            )
            uncertain = (
                not compatible
                or missing
                or base["status"] == "UNKNOWN"
                or candidate["status"] == "UNKNOWN"
                or not b
                or not c
            )
            verdict = "FAIL" if regressions else "UNKNOWN" if uncertain else "PASS"
            return self._save(
                {
                    "kind": "regression",
                    "status": verdict,
                    "checks": [],
                    "baseline_id": baseline_id,
                    "candidate_id": candidate_id,
                    "new_regressions": regressions,
                    "missing_checks": missing,
                    "compatible_profiles": compatible,
                    "identical_input": base.get("artifact", {}).get("sha256")
                    == candidate.get("artifact", {}).get("sha256"),
                    "scope": "Only comparable recorded checks; not a release verdict",
                }
            )
