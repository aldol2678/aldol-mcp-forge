"""Real loopback MCP Streamable HTTP integration test, no external network."""
import json
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request

TOKEN = "q" * 50


class LiveHttpMcpTests(unittest.TestCase):
    def test_bearer_protected_real_http_sdk_client(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = {**os.environ, "ALDOL_SEUM_MCP_BEARER_TOKEN": TOKEN,
               "ALDOL_SEUM_HTTP_PROBE_ENABLED": "1",
               "ALDOL_SEUM_GITHUB_READ_ENABLED": "0",
               "ALDOL_SEUM_STARTUP_PROBE_ENABLED": "0",
               "ALDOL_SEUM_PUBLIC_HOST": "", "RAILWAY_PUBLIC_DOMAIN": "",
               "PORT": str(port), "PYTHONDONTWRITEBYTECODE": "1"}
        process = subprocess.Popen(
            [sys.executable, "-B", "-m", "enterprise_mcps.http_server"],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        root = "http://127.0.0.1:" + str(port)
        try:
            deadline = time.monotonic() + 38
            ready = False
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                try:
                    with urllib.request.urlopen(root + "/healthz", timeout=2) as response:
                        ready = response.status == 200
                    if ready:
                        break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(0.2)
            self.assertTrue(ready, "Server did not become healthy")
            with self.assertRaises(urllib.error.HTTPError) as response:
                urllib.request.urlopen(root + "/mcp", timeout=3)
            self.assertEqual(response.exception.code, 401)
            done = False
            final = None
            while time.monotonic() < deadline:
                req = urllib.request.Request(root + "/status",
                          headers={"Authorization": "Bearer " + TOKEN})
                with urllib.request.urlopen(req, timeout=3) as response:
                    final = json.load(response)
                if final["authenticated_http_probe"]["status"] in ("PASS", "FAIL"):
                    done = True
                    break
                time.sleep(0.35)
            self.assertTrue(done, "Authenticated MCP HTTP probe timed out")
            self.assertEqual(final["startup_probe"]["status"], "SKIP")
            self.assertEqual(final["authenticated_http_probe"]["status"], "PASS", final)
            self.assertEqual(final["authenticated_http_probe"]["discovered_tools"], 3)
        finally:
            process.terminate()
            try:
                _, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                _, stderr = process.communicate(timeout=3)
            if process.returncode not in (0, -15, 143):
                # No secret should ever be printed; only concise service error context.
                self.fail("Unexpected SEUM HTTP server termination: " + str(process.returncode)
                          + " stderr tail: " + stderr.decode(errors="replace")[-1500:])


if __name__ == "__main__":
    unittest.main(verbosity=2)
