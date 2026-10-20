"""Stateless, synchronous Forge official SDK verifier for Cloud Run.

Deploy as an ISOLATED Cloud Run service in the existing aram-slack-bridge-2026
GCP project. Never replace or modify slack-bridge-receiver or /slack/events.
This service holds NO jobs, credentials or ZIPs between requests. The existing
owner-authenticated Sites R2 bucket stores verified results after the HTTPS call.

Request-based Cloud Run CPU is sufficient because this handler holds the HTTP
connection open until both official SDK transports finish. No background threads.
"""
from __future__ import annotations

import base64
import binascii
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import subprocess
import threading
from zipfile import BadZipFile
import time

from bridge.sdk_job_gateway import encode_json, verify_signature, MAX_BODY
from ci.verify_studio_archive import verify

PATH = "/v1/sdk/jobs"
SHA = re.compile(r"^[0-9a-f]{64}$")
PROJECT = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MAX_ZIP_BYTES = 1_000_000
MAX_ENCODED_BYTES = 1_350_000


def verify_request(value: object) -> tuple[bytes, str, str, str]:
    if not isinstance(value, dict) or set(value) != {
        "subject_hash", "project_id", "sha256", "zip_base64"
    }:
        raise ValueError("Unsupported request body")
    subject, project, expected, encoded = (
        value["subject_hash"], value["project_id"], value["sha256"],
        value["zip_base64"]
    )
    if (not all(isinstance(x, str) for x in (subject, project, expected, encoded))
        or not SHA.fullmatch(subject) or not PROJECT.fullmatch(project)
        or not SHA.fullmatch(expected) or len(encoded) > MAX_ENCODED_BYTES):
        raise ValueError("Invalid subject, project, hash or encoded size")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid base64 ZIP") from exc
    if not raw or len(raw) > MAX_ZIP_BYTES or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("ZIP size or SHA-256 mismatch")
    return raw, subject, project, expected


def run_sync(value: object) -> dict:
    raw, subject, project, sha = verify_request(value)
    job_id = hashlib.sha256(f"{subject}:{project}:{sha}".encode()).hexdigest()
    created_at = int(time.time())
    # Cloud Run's writable /tmp is ephemeral. Never assume it persists.
    with tempfile.TemporaryDirectory(prefix="forge-sdk-cloudrun-") as folder:
        archive = Path(folder) / "export.zip"
        archive.write_bytes(raw)
        try:
            report = verify(str(archive))
        except subprocess.TimeoutExpired:
            report = {"passed": False, "official_sdk": "TIMEOUT"}
        except RuntimeError:
            report = {"passed": False, "official_sdk": "FAIL"}
    passed = (report.get("passed") is True
              and report.get("official_sdk") == "PASS"
              and report.get("inmemory") == "PASS"
              and report.get("stdio") == "PASS"
              and report.get("network_used") is False
              and report.get("sdk_version") == "2.0.0")
    verification = {
        key: report[key] for key in (
            "passed", "official_sdk", "sdk_version", "inmemory", "stdio",
            "network_used", "files_checked", "kind", "version"
        ) if key in report
    }
    final_status = "PASS" if passed else "TIMEOUT" if report.get("official_sdk") == "TIMEOUT" else "FAIL"
    if not passed:
        verification = {"passed": False, "official_sdk": final_status}
    return {
        "job_id": job_id, "project_id": project, "sha256": sha,
        "status": final_status, "verification": verification,
        "created_at": created_at, "finished_at": int(time.time()),
    }


def make_handler(secret: str):
    if not isinstance(secret, str) or len(secret) < 32:
        raise ValueError("FORGE_SDK_BRIDGE_SECRET requires at least 32 characters")

    # One verifier mutates the trusted generator's global project root at a time.
    # Replayed signed requests reuse their final response instead of executing again.
    gate = threading.Lock()
    recent = {}

    class Handler(BaseHTTPRequestHandler):
        server_version = "ForgeCloudSDK/0.1"
        sys_version = ""

        def log_message(self, fmt, *args):
            # Neither user scope nor ZIP content nor credentials are logged.
            return

        def reply(self, status: int, payload: dict):
            raw = encode_json(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            # Health is intentionally not a free authentication oracle.
            self.reply(404, {"error": "Not found"})

        def do_POST(self):
            if self.path != PATH:
                self.reply(404, {"error": "Not found"})
                return
            # Sites server-to-server only; do not accept browser-origin posts.
            if self.headers.get("Origin"):
                self.reply(403, {"error": "Forbidden"})
                return
            length = self.headers.get("Content-Length", "")
            if not length.isdecimal() or not (0 < int(length) <= MAX_BODY):
                self.reply(413, {"error": "Body limit"})
                return
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                self.reply(415, {"error": "JSON required"})
                return
            self.connection.settimeout(10)
            raw = self.rfile.read(int(length))
            if not verify_signature(secret, self.headers.get("X-Forge-Timestamp", ""),
                                    PATH, raw, self.headers.get("X-Forge-Signature", "")):
                self.reply(401, {"error": "Unauthorized"})
                return
            if not gate.acquire(blocking=False):
                self.reply(429, {"error": "Verifier busy"})
                return
            try:
                now = time.monotonic()
                for k in list(recent):
                    if recent[k][0] < now:
                        del recent[k]
                receipt = hashlib.sha256((self.headers.get("X-Forge-Timestamp", "") + "\n").encode() + raw).hexdigest()
                if receipt in recent:
                    self.reply(200, recent[receipt][1])
                    return
                data = json.loads(raw)
                output = run_sync(data)
                if len(recent) >= 128:
                    recent.pop(next(iter(recent)))
                recent[receipt] = (now + 90, output)
                self.reply(200, output)
            except (ValueError, TypeError, json.JSONDecodeError, BadZipFile, KeyError):
                self.reply(400, {"error": "Invalid artifact"})
            except Exception:
                # Never leak project code, filesystem paths or subprocess logs.
                self.reply(503, {"error": "Verification unavailable"})
            finally:
                gate.release()

    return Handler


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    if port < 1 or port > 65535:
        raise ValueError("Invalid Cloud Run port")
    secret = os.environ.get("FORGE_SDK_BRIDGE_SECRET", "")
    # 0.0.0.0 is required for Cloud Run's ingress. The app always enforces
    # HMAC and Cloud Run ingress/IAM must be configured separately.
    server = ThreadingHTTPServer(("0.0.0.0", port), make_handler(secret))
    server.serve_forever()


if __name__ == "__main__":
    main()
