"""Network-free tests for the opt-in GitHub reader, with a mocked REST response."""
import asyncio
import base64
import hashlib
import json
import os
import unittest
from unittest.mock import patch

from enterprise_mcps import github_read, seum
from enterprise_mcps.server import create_app


class Response:
    status = 200
    headers = {"Content-Type": "application/json; charset=utf-8"}

    def __init__(self, obj):
        self.payload = json.dumps(obj).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, n):
        return self.payload[:n]


class Opener:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return self.response


SOURCE = 'def main():\n    eval("1+1")\n'
BYTES = SOURCE.encode("utf-8")
SHA = hashlib.sha1(b"blob " + str(len(BYTES)).encode() + b"\0" + BYTES).hexdigest()
LOCATOR = {"source": "github", "owner": "aldol2678", "repo": "aldol-mcp-forge",
           "path": "src/check.py", "ref": "main"}


def document(content=BYTES, sha=SHA, size=None):
    return {"type": "file", "encoding": "base64",
            "content": base64.b64encode(content).decode(),
            "sha": sha, "size": len(content) if size is None else size}


class GitHubReadTests(unittest.TestCase):
    def mock_read(self, doc):
        opener = Opener(Response(doc))
        return patch.object(github_read.urllib.request, "build_opener", return_value=opener), opener

    def test_disabled_by_default_without_network(self):
        with patch.dict(os.environ, {"ALDOL_SEUM_GITHUB_READ_ENABLED": "0"}, clear=True):
            with patch.object(github_read.urllib.request, "build_opener") as opener:
                with self.assertRaisesRegex(ValueError, "GITHUB_READ_DISABLED"):
                    github_read.read_file(LOCATOR)
                opener.assert_not_called()

    def test_only_safe_fixed_host_ref_and_path(self):
        bad = [
            {"owner": "https://evil.example"},
            {"repo": "../../secrets"},
            {"path": "../.env"},
            {"path": "docs//secret.py"},
            {"path": ".github/workflows/main.yml"},
            {"ref": "x..y"},
            {"ref": "refs//heads/main"},
            {"ref": "https://evil.example"},
            {"ref": ".hidden"},
        ]
        with patch.dict(os.environ, {"ALDOL_SEUM_GITHUB_READ_ENABLED": "1"}, clear=True):
            with patch.object(github_read.urllib.request, "build_opener") as opener:
                for override in bad:
                    with self.subTest(override=override), self.assertRaises(ValueError):
                        github_read.read_file({**LOCATOR, **override})
                opener.assert_not_called()

    def test_real_decode_hash_and_provenance_without_leaking_token(self):
        mock, opener = self.mock_read(document())
        with patch.dict(os.environ, {"ALDOL_SEUM_GITHUB_READ_ENABLED": "1",
                                     "ALDOL_SEUM_GITHUB_TOKEN": "top-secret-token"}, clear=True), mock:
            result = github_read.read_file(LOCATOR)
        self.assertEqual(result["content"], SOURCE)
        self.assertEqual(result["git_blob_sha"], SHA)
        self.assertEqual(result["sha256"], hashlib.sha256(BYTES).hexdigest())
        self.assertTrue(result["credentialed"])
        self.assertEqual(len(opener.requests), 1)
        request, timeout = opener.requests[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(timeout, 6)
        self.assertTrue(request.full_url.startswith(
            "https://api.github.com/repos/aldol2678/aldol-mcp-forge/contents/src/check.py?"))
        self.assertNotIn("top-secret", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer top-secret-token")
        self.assertEqual(result["fetch_scope"], "single-file-read-only")

    def test_rejects_metadata_for_directory_blob_mismatch_and_oversize(self):
        variants = [
            {**document(), "type": "dir"},
            document(sha="0" * 40),
            document(size=5000),
            document(size=1),
            {**document(), "encoding": "none"},
            {**document(), "content": "@invalid@"},
            document(content=b"\xff\xfe"),
        ]
        with patch.dict(os.environ, {"ALDOL_SEUM_GITHUB_READ_ENABLED": "1"}, clear=True):
            for doc in variants:
                mock, _ = self.mock_read(doc)
                with self.subTest(doc=str(doc)[:100]), mock, self.assertRaises(ValueError):
                    github_read.read_file(LOCATOR)

    def test_locally_passed_source_retains_original_semantics(self):
        with patch.dict(os.environ, {"ALDOL_SEUM_GITHUB_READ_ENABLED": "0"}, clear=True):
            result = seum.analyze_code(json.dumps({
                "path": "src/local.py", "language": "python", "content": SOURCE}))
        self.assertEqual(json.loads(result["summary"])["method"], "offline-static-only")
        self.assertNotIn("github_provenance", json.loads(result["summary"]))

    def test_github_file_is_actually_analyzed_and_identified(self):
        mock, _ = self.mock_read(document())
        with patch.dict(os.environ, {"ALDOL_SEUM_GITHUB_READ_ENABLED": "1"}, clear=True), mock:
            result = seum.analyze_code(json.dumps(LOCATOR))
        summary = json.loads(result["summary"])
        self.assertEqual(summary["method"], "github-readonly-static")
        self.assertEqual(summary["github_provenance"]["git_blob_sha"], SHA)
        self.assertIn("DYNAMIC_EXECUTION", [x["code"] for x in json.loads(result["risks"])])
        self.assertFalse(summary.get("tests_executed", False))

    def test_sdk_inmemory_reads_mocked_github_without_writes(self):
        try:
            from mcp import Client
        except ImportError:
            self.skipTest("Official Python MCP SDK unavailable")
        async def run():
            async with Client(create_app("seum"), raise_exceptions=True) as client:
                return await client.call_tool("analyze_code",
                                               {"repository": json.dumps(LOCATOR)})
        mock, opener = self.mock_read(document())
        with patch.dict(os.environ, {"ALDOL_SEUM_GITHUB_READ_ENABLED": "1"}, clear=True), mock:
            reply = asyncio.run(run())
        self.assertFalse(reply.is_error, reply)
        result = reply.structured_content
        if "result" in result and isinstance(result["result"], dict):
            result = result["result"]
        self.assertEqual(json.loads(result["summary"])["github_provenance"]["git_blob_sha"], SHA)
        self.assertEqual(len(opener.requests), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
