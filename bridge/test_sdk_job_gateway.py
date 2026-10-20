"""Real HTTP/HMAC async SDK service verification using Worker-exported ZIPs."""
from http.client import HTTPConnection
import base64
import hashlib
import hmac
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.sdk_job_gateway import JobStore, make_handler, verify_signature

SAMPLE = ROOT / "ci-results" / "studio-sdk-fixtures" / "studio-curated-v021.zip"
SECRET = "sdk-gateway-local-ci-secret-" + ("x" * 48)


class SDKJobGatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = JobStore(self.temp.name, SECRET)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.store))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def call(self, path, body, valid=True, timestamp=None):
        raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
        stamp = str(int(time.time()) if timestamp is None else timestamp)
        signature = hmac.new(SECRET.encode(), stamp.encode() + b"\n" +
                             path.encode() + b"\n" + raw, hashlib.sha256).hexdigest()
        if not valid:
            signature = "0" * 64
        conn = HTTPConnection(*self.server.server_address, timeout=20)
        conn.request("POST", path, body=raw, headers={
            "Content-Type": "application/json",
            "X-Forge-Timestamp": stamp,
            "X-Forge-Signature": signature,
        })
        response = conn.getresponse()
        data = json.loads(response.read())
        code = response.status
        conn.close()
        return code, data

    def create_body(self, subject=None, project=None):
        data = SAMPLE.read_bytes()
        return {
            "subject_hash": subject or "a" * 64,
            "project_id": project or str(uuid4()),
            "sha256": hashlib.sha256(data).hexdigest(),
            "zip_base64": base64.b64encode(data).decode(),
        }

    def test_hmac_timestamp_and_exact_body(self):
        path = "/v1/sdk/jobs"
        self.assertFalse(verify_signature(SECRET, "abc", path, b"{}", "0" * 64))
        self.assertFalse(verify_signature(SECRET, str(int(time.time())-500),
                         path, b"{}", "0" * 64))
        code, _ = self.call(path, self.create_body(), valid=False)
        self.assertEqual(code, 401)
        code, _ = self.call(path, self.create_body(), timestamp=int(time.time())-500)
        self.assertEqual(code, 401)

    def test_reject_tampering_and_bad_ids(self):
        body = self.create_body()
        body["sha256"] = "0" * 64
        self.assertEqual(self.call("/v1/sdk/jobs", body)[0], 400)
        body = self.create_body()
        body["subject_hash"] = "../admin"
        self.assertEqual(self.call("/v1/sdk/jobs", body)[0], 400)
        body = self.create_body()
        body["owner_id"] = "attacker"
        self.assertEqual(self.call("/v1/sdk/jobs", body)[0], 400)
        self.assertEqual(self.store.active, 0)

    def test_async_real_sdk_result_and_cross_user_rejection(self):
        body = self.create_body()
        code, created = self.call("/v1/sdk/jobs", body)
        self.assertEqual(code, 202, created)
        self.assertEqual(created["status"], "QUEUED")
        jid = created["job_id"]
        self.assertEqual(self.call("/v1/sdk/jobs", body)[1]["job_id"], jid)
        query = {"subject_hash": body["subject_hash"],
                 "project_id": body["project_id"], "job_id": jid}
        status = None
        for _ in range(120):
            _, status = self.call("/v1/sdk/jobs/status", query)
            if status["status"] not in ("QUEUED", "RUNNING"):
                break
            time.sleep(0.2)
        self.assertEqual(status["status"], "PASS", status)
        self.assertEqual(status["verification"]["official_sdk"], "PASS")
        self.assertEqual(status["verification"]["inmemory"], "PASS")
        self.assertEqual(status["verification"]["stdio"], "PASS")
        self.assertFalse(status["verification"]["network_used"])
        self.assertEqual(self.call("/v1/sdk/jobs/status", {
            **query, "subject_hash": "b" * 64,
        })[0], 404)
        self.assertFalse((self.store.job_directory(body["subject_hash"], jid) / "export.zip").exists())


if __name__ == "__main__":
    unittest.main()
