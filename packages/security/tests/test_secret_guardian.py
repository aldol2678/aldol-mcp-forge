"""Secret Guardian credential-redaction and read-only contract tests."""
import datetime as dt
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import secret_guardian as g

class GuardianTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"ALDOL_SECURITY_ROOT": self.tmp.name})
        self.env.start()
        self.clock = patch("secret_guardian._now", return_value=dt.date(2026, 10, 23))
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        self.env.stop()
        self.tmp.cleanup()

    def manifest(self, credentials):
        (self.root / g.MANIFEST).write_text(
            json.dumps({"schema_version": 1, "credentials": credentials}), encoding="utf-8")

    def test_no_inventory_not_secure(self):
        self.assertEqual(g.report()["status"], "UNKNOWN")

    def test_risk_codes_and_severity(self):
        self.manifest([{"ref": "prod-1", "provider": "openai", "privilege": "admin",
                        "owner": "team", "last_rotated_at": "2025-01-01",
                        "expires_at": "2026-01-01", "rotation_policy_days": 90,
                        "exposure_status": "suspected"}])
        result = g.report()
        codes = {x["code"] for x in result["risks"]}
        self.assertEqual(result["status"], "FINDINGS")
        self.assertTrue({"USER_REPORTED_EXPOSURE", "EXPIRED_BY_METADATA",
                         "ROTATION_OVERDUE_BY_METADATA", "BROAD_PRIVILEGE_REVIEW"} <= codes)

    def test_env_redaction_and_unrelated_names(self):
        secret = "SENSITIVE_VALUE_NOT_FOR_OUTPUT"
        (self.root / ".env").write_text("OPENAI_API_KEY=" + secret + "\nPORT=4000\n")
        out = g.report()
        serialized = json.dumps(out)
        self.assertEqual(out["credential_count"], 1)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)
        self.assertNotIn(str(self.root), serialized)

    def test_env_template_ignored(self):
        (self.root / ".env.example").write_text("GITHUB_TOKEN=placeholder\n")
        self.assertEqual(g.report()["credential_count"], 0)

    def test_world_readable_env_flagged(self):
        path = self.root / ".env"
        path.write_text("GITHUB_TOKEN=secret\n")
        path.chmod(0o644)
        self.assertIn("DOTENV_WORLD_READABLE", {i["code"] for i in g.report()["risks"]})

    def test_unknown_rotation_not_clean(self):
        self.manifest([{"ref": "token1", "provider": "github"}])
        self.assertIn("ROTATION_DATE_UNKNOWN", {i["code"] for i in g.report()["risks"]})

    def test_unexpected_secret_field_fail_closed(self):
        marker = "EXFIL_DO_NOT_EXPOSE"
        self.manifest([{"ref": "token1", "api_key": marker}])
        out = g.report()
        self.assertEqual(out["status"], "INCOMPLETE")
        self.assertNotIn(marker, json.dumps(out))

    def test_symlink_and_traversal_block(self):
        self.assertEqual(g.report("../")["status"], "BLOCKED")
        (self.root / "outside").symlink_to("/etc")
        self.assertEqual(g.report()["status"], "BLOCKED")

    def test_date_failure_is_incomplete(self):
        self.manifest([{"ref": "token1", "last_rotated_at": "2099-01-01"}])
        self.assertEqual(g.report()["status"], "INCOMPLETE")

    def test_never_write_workspace(self):
        (self.root / ".env").write_text("OPENAI_API_KEY=fake\n")
        before = list(self.root.iterdir())
        g.report()
        self.assertEqual(before, list(self.root.iterdir()))

if __name__ == "__main__":
    unittest.main()
