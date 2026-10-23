"""Loopback HTTP integration checks using synthetic credentials only.

Starts the real HTTP Handler against a temporary workspace. This is NOT a
production deployment, actual secret scan, browser-device test, or remote MCP.
"""
from __future__ import annotations
import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from http.server import ThreadingHTTPServer
from http_api import Handler, LOCK

FAKE_TOKEN = "LOCAL_TEST_ONLY_" + "a" * 42
FAKE_VALUE = "FAKE_ONLY_NEVER_A_REAL_SECRET_123456"
HERE = Path(__file__).resolve().parent

class TestLoopbackHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="aldol-sg-http-")
        cls.root = Path(cls.temporary.name)
        (cls.root / ".env").write_text("OPENAI_API_KEY=" + FAKE_VALUE + "\nPORT=3000\n", encoding="utf-8")
        (cls.root / ".env").chmod(0o600)
        (cls.root / "secret-guardian.inventory.json").write_text(
            json.dumps({"schema_version": 1, "credentials": [{
                "ref": "test_prod_token", "provider": "openai",
                "environment": "test", "privilege": "read", "owner": "test",
                "last_rotated_at": "2026-10-01", "exposure_status": "unknown"
            }]}), encoding="utf-8")
        cls.env = patch.dict(os.environ, {"ALDOL_SECURITY_ROOT": str(cls.root),
                                          "ALDOL_SECURITY_TOKEN": FAKE_TOKEN,
                                          "ALDOL_SECURITY_OSV_NETWORK": "0"})
        cls.env.start()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.env.stop()
        cls.temporary.cleanup()

    def call(self, method, path, payload=None, token=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        if payload is not None:
            headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            data = response.read()
            return response.status, dict(response.getheaders()), data
        finally:
            connection.close()

    def test_health_is_unchanged(self):
        code, headers, content = self.call("GET", "/health")
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(content)["status"], "alive")
        self.assertEqual(headers.get("Cache-Control"), "no-store")

    def test_denies_unauthenticated_and_wrong_token(self):
        for supplied in (None, "wrong", "x" * 300):
            code, headers, body = self.call("GET", "/api/capabilities", token=supplied)
            self.assertEqual(code, 401)
            self.assertEqual(headers.get("Cache-Control"), "no-store")
            self.assertNotIn(FAKE_VALUE.encode(), body)
            code, _, body = self.call(
                "POST", "/api/scan", {"tool": "guardian", "subpath": "."}, supplied)
            self.assertEqual(code, 401)
            self.assertNotIn(FAKE_VALUE.encode(), body)

    def test_authenticated_legacy_capabilities(self):
        code, _, content = self.call("GET", "/api/capabilities", token=FAKE_TOKEN)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(content)["name"], "ALDOL SECURITY")

    def test_guardian_response_redacted_and_readonly(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        code, headers, body = self.call(
            "POST", "/api/scan", {"tool": "guardian", "subpath": "."}, FAKE_TOKEN)
        self.assertEqual(code, 200)
        self.assertIn("application/json", headers["Content-Type"])
        result = json.loads(body)
        self.assertEqual(result["module"], "Secret Guardian")
        self.assertEqual(result["credential_count"], 2)
        self.assertNotIn(FAKE_VALUE.encode(), body)
        self.assertNotIn(b"OPENAI_API_KEY", body)
        self.assertNotIn(str(self.root).encode(), body)
        self.assertNotIn(b"test_prod_token", body)
        after = {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        self.assertEqual(before, after, "HTTP read-only mode must not change workspace")

    def test_path_escape_and_invalid_input_fail_closed(self):
        code, _, content = self.call(
            "POST", "/api/scan", {"tool": "guardian", "subpath": "../"}, FAKE_TOKEN)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(content)["status"], "BLOCKED")
        code, _, _ = self.call(
            "POST", "/api/scan", {"tool": "guardian", "evil": "value"}, FAKE_TOKEN)
        self.assertEqual(code, 400)
        code, _, _ = self.call(
            "POST", "/api/scan", {"tool": "guardian", "subpath": "x" * 4000}, FAKE_TOKEN)
        self.assertEqual(code, 413)

    def test_legacy_osv_defaults_blocked_without_network(self):
        code, _, content = self.call(
            "POST", "/api/scan", {"tool": "osv", "subpath": "."}, FAKE_TOKEN)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(content)["status"], "BLOCKED")

    def test_mobile_assets_served_and_guardian_selectable(self):
        code, headers, html = self.call("GET", "/")
        self.assertEqual(code, 200)
        self.assertIn(b'value="guardian"', html)
        self.assertIn(b'name="viewport"', html)
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        code, _, script = self.call("GET", "/mobile.js")
        self.assertEqual(code, 200)
        self.assertIn(b"addEventListener", script)

    def test_mobile_script_sends_real_loopback_request(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required for UI client integration test")
        origin = "http://127.0.0.1:" + str(self.port)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
               "ALDOL_TEST_HTTP_ORIGIN": origin,
               "ALDOL_TEST_HTTP_TOKEN": FAKE_TOKEN}
        result = subprocess.run([node, str(HERE / "mobile_http_client.mjs")],
                                cwd=str(HERE), env=env, timeout=20, capture_output=True,
                                text=True, check=False)
        self.assertEqual(result.returncode, 0,
                         "Node mobile flow failed (details omitted to avoid data leaks)")

    def raw_call(self, body, extra_headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {'Authorization': 'Bearer ' + FAKE_TOKEN, 'Content-Type': 'application/json'}
        headers.update(extra_headers or {})
        try:
            connection.request('POST', '/api/scan', body=body, headers=headers)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_malformed_json_types_and_framing(self):
        for raw in (b'{', b'\xff', b'[]', b'null', b'{"tool":[]}', b'{"subpath":1}',
                    b'{"tool":"guardian","tool":"all"}', b'{"tool":NaN}',
                    b'[' * 1000 + b']' * 1000):
            self.assertEqual(self.raw_call(raw)[0], 400)
        self.assertEqual(self.raw_call(b'{}', {'Transfer-Encoding': 'chunked'})[0], 400)
        self.assertEqual(self.raw_call(b'{}', {'Content-Type': 'text/plain'})[0], 400)
        self.assertEqual(self.raw_call(b'', {'Content-Length': '0'})[0], 413)
        self.assertEqual(self.raw_call(b'', {'Content-Length': '2049'})[0], 413)
        self.assertEqual(self.raw_call(b'', {'Content-Length': 'invalid'})[0], 400)

    def test_non_ascii_auth_rejected_without_exception(self):
        self.assertEqual(self.call('POST', '/api/scan', {'tool': 'guardian'}, '\u00e9' * 40)[0], 401)

    def test_duplicate_headers_and_protocol_errors_sanitized(self):
        for duplicate, expected in (('Authorization', 401), ('Content-Length', 400)):
            connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
            try:
                connection.putrequest('POST', '/api/scan')
                for name, value in (('Authorization', 'Bearer ' + FAKE_TOKEN),
                                    ('Content-Length', '2'), ('Content-Type', 'application/json')):
                    connection.putheader(name, value)
                    if name == duplicate:
                        connection.putheader(name, value)
                connection.endheaders(b'{}')
                response = connection.getresponse()
                self.assertEqual(response.status, expected)
                response.read()
            finally:
                connection.close()
        code, _, body = self.call('SYNTHETIC_PRIVATE_METHOD', '/private-path')
        self.assertEqual(code, 501)
        self.assertNotIn(b'SYNTHETIC_PRIVATE_METHOD', body)
        self.assertNotIn(b'/private-path', body)

    def test_incomplete_body_times_out(self):
        original = Handler.setup
        def short_timeout(handler):
            original(handler)
            handler.connection.settimeout(0.1)
        with patch.object(Handler, 'setup', short_timeout):
            self.assertEqual(self.raw_call(b'{', {'Content-Length': '10'})[0], 408)

    def test_concurrent_scan_rejected_and_slot_released(self):
        entered, release = threading.Event(), threading.Event()
        replies = []
        def slow(_):
            entered.set()
            if not release.wait(4):
                raise RuntimeError('synthetic timeout')
            return {'status': 'UNKNOWN'}
        with patch('http_api.guardian_report', side_effect=slow):
            worker = threading.Thread(target=lambda: replies.append(self.call(
                'POST', '/api/scan', {'tool': 'guardian'}, FAKE_TOKEN)[0]))
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                self.assertEqual(self.call('POST', '/api/scan', {'tool': 'guardian'}, FAKE_TOKEN)[0], 429)
            finally:
                release.set()
                worker.join(5)
        self.assertEqual(replies, [200])
        self.assertTrue(LOCK.acquire(blocking=False))
        LOCK.release()

    def test_internal_failure_sanitized_and_recovers(self):
        import contextlib
        import io
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured), patch('http_api.guardian_report',
                side_effect=RuntimeError(FAKE_VALUE + str(self.root))):
            code, _, body = self.call('POST', '/api/scan', {'tool': 'guardian'}, FAKE_TOKEN)
        self.assertEqual(code, 500)
        for marker in (FAKE_VALUE, str(self.root), FAKE_TOKEN):
            self.assertNotIn(marker, body.decode() + captured.getvalue())
        self.assertEqual(self.call('POST', '/api/scan', {'tool': 'guardian'}, FAKE_TOKEN)[0], 200)

    def test_existing_scanner_http_dispatch_and_aggregation(self):
        # Real HTTP, mocked external executables: no network/database claims.
        reports = {'trivy': {'Results': []}, 'osv': {'results': []},
                   'syft': {'components': [{}, {}]}}
        with patch.dict(os.environ, {'ALDOL_SECURITY_OSV_NETWORK': '1'}), \
                patch('engine._invoke', side_effect=lambda name, *args: reports[name]):
            for tool, status in (('trivy', 'NO_FINDINGS_IN_SCOPE'),
                                 ('osv', 'NO_FINDINGS_IN_SCOPE'), ('syft', 'INVENTORIED')):
                code, _, body = self.call('POST', '/api/scan', {'tool': tool}, FAKE_TOKEN)
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(body)['status'], status)
            code, _, body = self.call('POST', '/api/scan', {'tool': 'all'}, FAKE_TOKEN)
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(body)['overall'], 'NO_FINDINGS_IN_COMPLETED_CHECKS')

if __name__ == "__main__":
    unittest.main()
