"""Network-boundary smoke tests for the owner-private loopback gateway."""
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.gateway import make_handler


class PrivateBridgeHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.secret = "bridge-ci-test-only-secret-" + ("x" * 44)
        self.host = "127.0.0.1"
        self.server = ThreadingHTTPServer(
            (self.host, 0),
            make_handler(self.temp.name, "verified-owner", self.secret),
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def request(self, method, path, payload=None, auth=True, headers=None):
        connection = HTTPConnection(self.host, self.server.server_address[1], timeout=10)
        body = json.dumps(payload) if payload is not None else ""
        h = {"Content-Type": "application/json"}
        if auth:
            h["X-Forge-Bridge-Secret"] = self.secret
        h.update(headers or {})
        connection.request(method, path, body=body, headers=h)
        response = connection.getresponse()
        decoded = json.loads(response.read())
        connection.close()
        return response.status, decoded

    def test_denies_missing_secret_and_browser_origins(self):
        payload = {"tool": "forge_create", "arguments": {
            "project_name": "html-one", "description": "HTML 게임 검사"
        }}
        self.assertEqual(self.request("POST", "/v1/execute", payload, auth=False)[0], 401)
        self.assertEqual(self.request("POST", "/v1/execute", payload, headers={
            "Origin": "https://attacker.example"
        })[0], 403)
        self.assertFalse((Path(self.temp.name) / "tenants").exists())

    def test_does_not_accept_client_principal_or_direct_paths(self):
        for mutation in (
            {"subject": "another-user"},
            {"workspace_root": "/tmp"},
            {"bridge_secret": "unauthorized"},
        ):
            payload = {"tool": "forge_create", "arguments": {
                "project_name": "no-spoof", "description": "HTML 게임 검사"
            }, **mutation}
            with self.subTest(mutation=mutation):
                self.assertEqual(self.request("POST", "/v1/execute", payload)[0], 400)
        self.assertFalse((Path(self.temp.name) / "tenants").exists())

    def test_authenticated_local_mcp_creation(self):
        status, payload = self.request("POST", "/v1/execute", {
            "tool": "forge_create", "arguments": {
                "project_name": "from-gateway", "description": "HTML 게임 검사"
            }
        })
        self.assertEqual(status, 200, payload)
        self.assertIs(payload.get("ok"), True)
        self.assertTrue(payload["result"]["created"])
        self.assertNotIn("path", payload["result"])
        # Expected tool errors remain errors. They must not be mistaken for success.
        status, payload = self.request("POST", "/v1/execute", {
            "tool": "forge_create", "arguments": {
                "project_name": "from-gateway", "description": "HTML 게임 검사"
            }
        })
        self.assertEqual(status, 400, payload)
        self.assertIs(payload.get("ok"), False)

    def test_invalid_tool_and_local_health(self):
        status, payload = self.request("POST", "/v1/execute", {
            "tool": "execute_shell", "arguments": {"command": "whoami"}
        })
        self.assertEqual(status, 400)
        self.assertFalse(payload["ok"])
        status, payload = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["scope"], "owner-private")

    def test_missing_server_configuration_fails_closed(self):
        for args in [("", "owner", "x" * 50), ("/tmp", "", "x" * 50), ("/tmp", "owner", "weak")]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                make_handler(*args)


if __name__ == "__main__":
    unittest.main()
