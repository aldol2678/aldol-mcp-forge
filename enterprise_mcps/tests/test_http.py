"""ASGI HTTP auth boundary tests. No external HTTP, no real GitHub credentials."""
import asyncio
import importlib
import json
import os
import unittest
from unittest.mock import patch

TOKEN = "a" * 48


async def request(app, method, path, authorization=None):
    body = []
    hdrs = [(b"host", b"localhost:8080")]
    if authorization is not None:
        hdrs.append((b"authorization", authorization.encode("ascii")))
    scope = {
        "type": "http", "asgi": {"version": "3.0"},
        "http_version": "1.1", "method": method, "scheme": "http",
        "path": path, "raw_path": path.encode("ascii"), "root_path": "",
        "query_string": b"", "server": ("localhost", 8080),
        "client": ("127.0.0.1", 60000), "headers": hdrs,
    }
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    async def send(msg):
        body.append(msg)
    await app(scope, receive, send)
    status = next(x["status"] for x in body if x["type"] == "http.response.start")
    chunks = b"".join(x.get("body", b"") for x in body if x["type"] == "http.response.body")
    return status, json.loads(chunks) if chunks else None


class PrivateHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {"ALDOL_SEUM_MCP_BEARER_TOKEN": TOKEN,
             "ALDOL_SEUM_STARTUP_PROBE_ENABLED": "0",
             "ALDOL_SEUM_GITHUB_READ_ENABLED": "0"}, clear=True):
            cls.mod = importlib.import_module("enterprise_mcps.http_server")

    def test_private_runtime_requires_strong_secret(self):
        with patch.dict(os.environ, {"ALDOL_SEUM_MCP_BEARER_TOKEN": ""},
                        clear=True):
            with self.assertRaisesRegex(RuntimeError, "bearer token"):
                self.mod.create_http_app()

    def test_bearer_gate_and_unauthenticated_health(self):
        with patch.dict(os.environ, {"ALDOL_SEUM_MCP_BEARER_TOKEN": TOKEN,
             "ALDOL_SEUM_STARTUP_PROBE_ENABLED": "0"}, clear=True):
            app = self.mod.create_http_app()
            async def check():
                ok, health = await request(app, "GET", "/healthz")
                self.assertEqual(ok, 200)
                self.assertEqual(health["healthy"], True)
                for path in ("/mcp", "/status"):
                    status, output = await request(app, "GET", path)
                    self.assertEqual(status, 401)
                    self.assertEqual(output["error"], "authorization_required")
                    wrong, _ = await request(app, "GET", path, "Bearer bad")
                    self.assertEqual(wrong, 401)
                status, output = await request(app, "GET", "/status", "Bearer " + TOKEN)
                self.assertEqual(status, 200)
                self.assertTrue(output["official_sdk_runtime"])
                self.assertFalse(output["github_read_enabled"])
                status, _ = await request(app, "GET", "/nope", "Bearer " + TOKEN)
                self.assertEqual(status, 404)
            asyncio.run(check())

    def test_host_allowlist_fails_closed(self):
        with patch.dict(os.environ, {"ALDOL_SEUM_MCP_BEARER_TOKEN": TOKEN,
                                    "ALDOL_SEUM_PUBLIC_HOST": "evil..site"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "Invalid.*HOST"):
                self.mod.create_http_app()

    def test_startup_probe_is_opt_in_and_does_not_touch_network(self):
        with patch.dict(os.environ, {"ALDOL_SEUM_MCP_BEARER_TOKEN": TOKEN,
             "ALDOL_SEUM_STARTUP_PROBE_ENABLED": "0"}, clear=True):
            with patch("enterprise_mcps.seum.read_github_file") as fetch:
                self.mod.create_http_app()
                fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
