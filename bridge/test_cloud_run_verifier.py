"""Cloud Run synchronous backend: local HTTP HMAC and actual MCP SDK v2."""
import base64
import hashlib
import hmac
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest.mock import patch
import subprocess
from http.server import ThreadingHTTPServer
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.cloud_run_verifier import PATH, make_handler, run_sync

ZIP = ROOT / "ci-results/studio-sdk-fixtures/studio-curated-v021.zip"
SECRET = "local-cloudrun-verifier-unique-secret-" + "x" * 48


class TestCloudRunVerify(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(SECRET))
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=5)

    def payload(self, owner="a" * 64):
        data = ZIP.read_bytes()
        return {
            "subject_hash": owner,
            "project_id": str(uuid4()),
            "sha256": hashlib.sha256(data).hexdigest(),
            "zip_base64": base64.b64encode(data).decode(),
        }

    def post(self, payload, *, secret=SECRET, tamper=False):
        raw = json.dumps(payload, separators=(",", ":")).encode()
        stamp = str(int(time.time()))
        sig = hmac.new(secret.encode(), stamp.encode() + b"\n" +
                       PATH.encode() + b"\n" + raw, hashlib.sha256).hexdigest()
        if tamper:
            sig = "0" * 64
        conn = HTTPConnection(*self.srv.server_address, timeout=30)
        conn.request("POST", PATH, body=raw, headers={
            "Content-Type": "application/json", "X-Forge-Timestamp": stamp,
            "X-Forge-Signature": sig,
        })
        res = conn.getresponse()
        status, response = res.status, json.loads(res.read())
        conn.close()
        return status, response

    def test_real_sdk_in_one_http_request_without_background_thread(self):
        p = self.payload()
        status, report = self.post(p)
        self.assertEqual(status, 200)
        self.assertEqual(report["status"], "PASS", report)
        self.assertEqual(report["verification"]["official_sdk"], "PASS")
        self.assertEqual(report["verification"]["inmemory"], "PASS")
        self.assertEqual(report["verification"]["stdio"], "PASS")
        self.assertFalse(report["verification"]["network_used"])
        expected = hashlib.sha256(
            f'{p["subject_hash"]}:{p["project_id"]}:{p["sha256"]}'.encode()
        ).hexdigest()
        self.assertEqual(report["job_id"], expected)
        # Stateless repeated request yields same content-addressed ID.
        self.assertEqual(self.post(p)[1]["job_id"], expected)

    def test_cross_owner_ids_are_not_interchangeable(self):
        p = self.payload()
        other = dict(p, subject_hash="b" * 64)
        a = self.post(p)[1]
        b = self.post(other)[1]
        self.assertNotEqual(a["job_id"], b["job_id"])

    def test_timeout_is_a_final_result_not_transport_unavailable(self):
        p = self.payload()
        with patch("bridge.cloud_run_verifier.verify", side_effect=subprocess.TimeoutExpired("sdk", 80)):
            status, result = self.post(p)
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "TIMEOUT")
        self.assertEqual(result["verification"]["official_sdk"], "TIMEOUT")

    def test_sdk_version_must_be_exactly_pinned(self):
        with patch("bridge.cloud_run_verifier.verify", return_value={
            "passed": True, "official_sdk": "PASS", "inmemory": "PASS",
            "stdio": "PASS", "network_used": False, "sdk_version": "2.1.0",
        }):
            self.assertEqual(run_sync(self.payload())["status"], "FAIL")

    def test_auth_and_bad_artifact_rejection(self):
        self.assertEqual(self.post(self.payload(), tamper=True)[0], 401)
        wrong = self.payload()
        wrong["sha256"] = "0" * 64
        self.assertEqual(self.post(wrong)[0], 400)
        wrong = self.payload()
        wrong["path"] = "../escape"
        self.assertEqual(self.post(wrong)[0], 400)
        self.assertEqual(self.post(self.payload(owner="../admin"))[0], 400)


if __name__ == "__main__":
    unittest.main()
