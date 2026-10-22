"""Private localhost API and mobile-first dashboard; NOT a public OAuth service."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import threading

from engine import capabilities, scan, scan_all

LOCK = threading.BoundedSemaphore(1)
MAX_REQUEST = 2048
HTML = Path(__file__).with_name("mobile.html")


class Handler(BaseHTTPRequestHandler):
    server_version = "ALDOLSecurity/0.1"

    def _headers(self, code: int, content_type: str = "application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'")
        self.end_headers()

    def _send(self, code: int, result: dict):
        data = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self._headers(code)
        self.wfile.write(data)

    def _authorized(self) -> bool:
        expected = os.environ["ALDOL_SECURITY_TOKEN"]
        supplied = self.headers.get("Authorization", "")
        return len(supplied) <= 260 and hmac.compare_digest(supplied, "Bearer " + expected)

    def do_GET(self):
        if self.path in ("/", "/mobile.html"):
            self._headers(200, "text/html; charset=utf-8")
            self.wfile.write(HTML.read_bytes())
        elif self.path == "/health":
            self._send(200, {"status": "alive", "version": "0.1.0"})
        elif self.path == "/api/capabilities":
            if not self._authorized():
                self._send(401, {"error": "unauthorized"})
                return
            self._send(200, capabilities())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/scan":
            self._send(404, {"error": "not found"})
            return
        if not self._authorized():
            self._send(401, {"error": "unauthorized"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_REQUEST:
                self._send(413, {"error": "invalid request size"})
                return
            data = json.loads(self.rfile.read(size).decode("utf-8"))
            if not isinstance(data, dict) or set(data) - {"tool", "subpath"}:
                raise ValueError("unexpected fields")
            tool = data.get("tool", "all")
            subpath = data.get("subpath", ".")
            if tool not in ("all", "trivy", "osv", "syft") or not isinstance(subpath, str):
                raise ValueError("invalid scan options")
        except (ValueError, UnicodeDecodeError):
            self._send(400, {"error": "invalid JSON or scan options"})
            return
        if not LOCK.acquire(blocking=False):
            self._send(429, {"error": "another scan is already running"})
            return
        try:
            result = scan_all(subpath) if tool == "all" else scan(tool, subpath)
            self._send(200, result)
        except Exception:
            self._send(500, {"error": "scan failed; internal details withheld"})
        finally:
            LOCK.release()

    def log_message(self, fmt, *args):
        # Do not log bearer token or workspace paths.
        return


def main():
    token = os.getenv("ALDOL_SECURITY_TOKEN", "")
    if len(token) < 32 or len(token) > 220:
        raise SystemExit("Set ALDOL_SECURITY_TOKEN to a random 32-220 character secret")
    if not os.getenv("ALDOL_SECURITY_ROOT"):
        raise SystemExit("Set ALDOL_SECURITY_ROOT to an allowed mounted workspace")
    host = os.getenv("ALDOL_SECURITY_HOST", "127.0.0.1")
    port = int(os.getenv("ALDOL_SECURITY_PORT", "8765"))
    if not 1 <= port <= 65535:
        raise SystemExit("invalid port")
    server = ThreadingHTTPServer((host, port), Handler)
    print("ALDOL SECURITY private dashboard listening", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
