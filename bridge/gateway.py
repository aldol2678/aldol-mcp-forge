"""Owner-private Forge bridge gateway, loopback-only and disabled by default.

This is NOT a public MCP server. A future Sites server-side adapter may connect
through an operator-controlled authenticated HTTPS reverse proxy, after the Site
identity and write authorization contract is independently verified.

This service never trusts identity, paths or credentials from model tool args.
"""
from __future__ import annotations

import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys

WORKER = Path(__file__).with_name("worker.py")
MAX_BODY = 160_000


def make_handler(root: str, owner_subject: str, secret: str):
    if len(secret) < 32 or not root or not owner_subject:
        raise ValueError("Bridge requires owner subject, workspace root and a strong secret")

    class Handler(BaseHTTPRequestHandler):
        server_version = "ForgePrivateBridge/0.1"
        sys_version = ""

        def log_message(self, fmt, *args):
            # Never log Authorization headers or bodies.
            return

        def send_json(self, status: int, body: dict):
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path == "/health":
                self.send_json(200, {"ready": True, "scope": "owner-private"})
            else:
                self.send_json(404, {"error": "Not found"})

        def do_POST(self):
            if self.path != "/v1/execute":
                self.send_json(404, {"error": "Not found"})
                return
            supplied = self.headers.get("X-Forge-Bridge-Secret") or ""
            if not hmac.compare_digest(supplied.encode(), secret.encode()):
                self.send_json(401, {"error": "Unauthorized"})
                return
            if self.headers.get("Origin"):
                self.send_json(403, {"error": "Browser-origin requests not accepted"})
                return
            length = self.headers.get("Content-Length", "")
            if not length.isdecimal() or not 0 < int(length) <= MAX_BODY:
                self.send_json(413, {"error": "Invalid request length"})
                return
            if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
                self.send_json(415, {"error": "JSON required"})
                return
            raw = self.rfile.read(int(length))
            # Only validated request tool+arguments are passed; the subject is
            # set in trusted server configuration and NEVER in the request.
            try:
                value = json.loads(raw)
            except (UnicodeDecodeError, ValueError):
                self.send_json(400, {"error": "Malformed JSON"})
                return
            if not isinstance(value, dict) or set(value) != {"tool", "arguments"}:
                self.send_json(400, {"error": "Request must contain tool and arguments only"})
                return
            # Neither the bridge secret nor other unrelated environment variables
            # are inherited by the Python subprocess.
            environment = {
                "PATH": os.environ.get("PATH", "/usr/bin"),
                "HOME": str(Path(root).resolve()),
                "LANG": "C.UTF-8",
                "PYTHONDONTWRITEBYTECODE": "1",
                "ALDOL_API_BASE_URL": "",
                "ALDOL_API_ALLOWED_HOST": "",
            }
            try:
                child = subprocess.run(
                    [sys.executable, "-B", str(WORKER),
                     "--workspace-root", root, "--subject", owner_subject],
                    input=json.dumps(value), text=True, capture_output=True,
                    timeout=100, check=False, env=environment,
                )
                body = json.loads(child.stdout)
                if child.returncode != 0 or body.get("ok") is not True:
                    self.send_json(400, {"ok": False, "error": body.get("error", "Worker failed")})
                else:
                    self.send_json(200, body)
            except (subprocess.TimeoutExpired, ValueError, OSError):
                self.send_json(503, {"error": "Worker execution failed"})

    return Handler


def main():
    secret = os.environ.get("FORGE_BRIDGE_SECRET", "")
    root = os.environ.get("FORGE_BRIDGE_WORKSPACE_ROOT", "")
    owner = os.environ.get("FORGE_BRIDGE_OWNER_SUBJECT", "")
    handler = make_handler(root, owner, secret)
    # A TLS reverse proxy on the SAME trusted host is required for any remote
    # connections. Never expose this listener directly to the internet.
    ThreadingHTTPServer(("127.0.0.1", 8765), handler).serve_forever()


if __name__ == "__main__":
    main()
