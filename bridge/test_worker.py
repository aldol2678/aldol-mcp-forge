"""Integration and safety tests for the private Python bridge worker."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge import worker

SPEC = (ROOT / "examples" / "pets_openapi.json").read_text(encoding="utf-8")


class BridgeWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def call(self, subject, tool, **args):
        return worker.run(str(self.root), subject, {"tool": tool, "arguments": args})

    def test_tool_contract_and_identity_rejection(self):
        bad = [
            {"tool": "forge_create", "arguments": {"project_name": "demo"}},
            {"tool": "forge_create", "arguments": {"project_name": "../escape", "description": "HTML"}},
            {"tool": "forge_create", "arguments": {"project_name": "demo", "description": "HTML", "root": "/tmp"}},
            {"tool": "forge_create", "arguments": {"project_name": "demo", "description": "HTML", "subject": "attacker"}},
            {"tool": "forge_import_openapi", "arguments": {"project_name": "demo", "spec_json": "{"}},
            {"tool": "forge_test", "arguments": {"project_name": "demo", "isolation": "unsafe"}},
            {"tool": "forge_package", "arguments": {"project_name": 1}},
            {"tool": "forge_delete", "arguments": {"project_name": "demo"}},
        ]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                worker.run(str(self.root), "owner-one", value)
        for subject in ("", "../owner", "owner/other", "💣"):
            with self.subTest(subject=subject), self.assertRaises(ValueError):
                worker.run(str(self.root), subject, {"tool": "forge_test", "arguments": {"project_name": "demo"}})

    def test_five_tools_end_to_end_and_tenant_isolation(self):
        subject = "trusted-owner-1"
        created = self.call(subject, "forge_create", project_name="hello-html", description="HTML 게임 검사")
        self.assertTrue(created["created"])
        self.assertNotIn("path", created)
        with self.assertRaises(ValueError):
            self.call(subject, "forge_create", project_name="hello-html", description="HTML 게임 검사")
        # Another subject must not see the first subject's project.
        with self.assertRaises(ValueError):
            self.call("trusted-owner-2", "forge_test", project_name="hello-html")

        updated = self.call(subject, "forge_add_tool", project_name="hello-html",
                            description="JSON 검사")
        self.assertTrue(updated["updated"])
        self.assertEqual(updated["tools"], ["html_audit", "json_audit"])
        self.assertNotIn("backup_path", updated)
        tested = self.call(subject, "forge_test", project_name="hello-html")
        self.assertTrue(tested["passed"])
        self.assertEqual(tested["compat_smoke_test"], "passed")
        if tested["sdk_available_locally"]:
            self.assertEqual(tested["official_sdk"], "passed")

        packed = self.call(subject, "forge_package", project_name="hello-html")
        self.assertTrue(packed["packaged"])
        self.assertTrue(packed["sha256"])
        self.assertEqual(packed["artifact_id"], packed["sha256"])
        self.assertGreater(packed["bytes"], 100)
        self.assertNotIn("path", packed)

        api = self.call(subject, "forge_import_openapi", project_name="pets-get",
                        spec_json=SPEC)
        self.assertTrue(api["created"])
        self.assertEqual(api["mode"], "dry_run_by_default")
        self.assertNotIn("path", api)
        result = self.call(subject, "forge_test", project_name="pets-get")
        self.assertTrue(result["passed"])
        self.assertFalse(result["default_network_access"])
        for row in result["sample_tool_results"].values():
            self.assertEqual(row["mode"], "dry_run")
            self.assertIs(row["network_called"], False)

        first = worker.private_workspace(str(self.root), subject)
        second = worker.private_workspace(str(self.root), "trusted-owner-2")
        self.assertNotEqual(first, second)
        self.assertTrue((first / "projects" / "hello-html").exists())
        self.assertFalse((second / "projects" / "hello-html").exists())

    def test_quota_rejection_prevents_extra_projects(self):
        space = worker.private_workspace(str(self.root), "quota-owner")
        projects = space / "projects"
        projects.mkdir()
        for i in range(20):
            (projects / f"test{i}").mkdir()
        with self.assertRaisesRegex(ValueError, "limit"):
            self.call("quota-owner", "forge_create", project_name="new-html", description="HTML 게임 검사")

    def test_symlink_and_subject_boundary(self):
        inner = self.root / "tenants"
        inner.symlink_to(self.root / "redirected")
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            worker.private_workspace(str(self.root), "trusted-owner")

    def test_json_process_does_not_accept_spoofed_subject(self):
        command = [sys.executable, str(ROOT / "bridge" / "worker.py"),
                   "--workspace-root", str(self.root), "--subject", "real-owner"]
        proc = subprocess.run(command, input=json.dumps({
            "tool": "forge_create",
            "arguments": {"project_name": "allowed", "description": "HTML 검사", "subject": "other"}
        }), capture_output=True, text=True, timeout=20)
        self.assertNotEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertFalse((self.root / "tenants").exists())


if __name__ == "__main__":
    unittest.main()
