import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import inspect_license, register_asset, check_usage, generate_credits, rights_report


class RightsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        os.environ["ALDOL_RIGHTS_DB"] = str(Path(self.temp.name) / "database.sqlite3")

    def tearDown(self):
        os.environ.pop("ALDOL_RIGHTS_DB", None)
        self.temp.cleanup()

    def asset(self, lic="CC-BY-4.0", **kwargs):
        return register_asset("Demo", "image", lic, "Author", source_url="https://example.org/source", evidence_url="https://example.org/proof", **kwargs)["asset_id"]

    def test_license_reference_no_certification(self):
        self.assertEqual(inspect_license("cc-by-4.0")["status"], "REFERENCE_ONLY")
        self.assertEqual(inspect_license("random")["status"], "UNKNOWN_LICENSE")

    def test_register_not_proven(self):
        self.assertEqual(register_asset("font", "font", "OWNED")["status"], "REGISTERED_UNVERIFIED")

    def test_reject_unhandled_license_and_kind(self):
        with self.assertRaises(ValueError): register_asset("x", "not-a-kind")
        with self.assertRaises(ValueError): register_asset("x", "image", "GPL")

    def test_reject_insecure_url(self):
        with self.assertRaises(ValueError): register_asset("x", "image", source_url="file:///etc/passwd")
        with self.assertRaises(ValueError): register_asset("x", "image", source_url="https://user:pass@example.org")

    def test_nc_blocks_commercial(self):
        result = check_usage(self.asset("CC-BY-NC-4.0"), commercial=True)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["legal_clearance"])

    def test_nd_private_modification_distinction(self):
        aid = self.asset("CC-BY-ND-4.0")
        self.assertNotEqual(check_usage(aid, modified=True, redistribute=False)["status"], "BLOCKED")
        self.assertEqual(check_usage(aid, modified=True, redistribute=True)["status"], "BLOCKED")

    def test_attribution_condition(self):
        aid = self.asset("CC-BY-4.0")
        self.assertEqual(check_usage(aid, attribution_planned=False)["status"], "CONDITIONAL")
        self.assertEqual(check_usage(aid, attribution_planned=True)["status"], "READY_FOR_HUMAN_REVIEW")

    def test_evidence_missing_overrides_credit(self):
        aid = register_asset("Demo", "image", "CC-BY-4.0")["asset_id"]
        self.assertEqual(check_usage(aid, attribution_planned=True)["status"], "NEEDS_EVIDENCE")

    def test_sa_requires_review(self):
        aid = self.asset("CC-BY-SA-4.0")
        self.assertEqual(check_usage(aid, modified=True, derivative_license="CC-BY-4.0", attribution_planned=True)["status"], "CONDITIONAL")
        self.assertEqual(check_usage(aid, modified=True, derivative_license="CC-BY-SA-4.0", attribution_planned=True)["status"], "READY_FOR_HUMAN_REVIEW")

    def test_unknown_not_cleared_even_with_evidence(self):
        aid = self.asset("CUSTOM")
        self.assertEqual(check_usage(aid, attribution_planned=True)["status"], "NEEDS_EVIDENCE")

    def test_draft_credits_identifies_missing(self):
        self.asset()
        register_asset("Unlicensed", "audio")
        result = generate_credits()
        self.assertEqual(result["count"], 2)
        self.assertTrue(result["incomplete"])
        self.assertEqual(result["status"], "DRAFT_REQUIRES_REVIEW")

    def test_software_and_font_licenses_require_human_review(self):
        for license_id in ("MIT", "APACHE-2.0", "OFL-1.1"):
            aid = self.asset(license_id)
            self.assertEqual(check_usage(aid)["status"], "READY_FOR_HUMAN_REVIEW")
            self.assertFalse(check_usage(aid)["legal_clearance"])

    def test_report_aggregates(self):
        self.asset("CC-BY-NC-4.0")
        self.asset("CC-BY-4.0")
        result = rights_report(commercial=True, attribution_planned=True)
        self.assertEqual(result["counts"]["BLOCKED"], 1)
        self.assertEqual(result["counts"]["READY_FOR_HUMAN_REVIEW"], 1)
        self.assertFalse(result["legal_clearance"])

    def test_missing_asset(self):
        self.assertEqual(check_usage("nonexistent")["status"], "NOT_FOUND")

    def test_prevent_sql_injection(self):
        register_asset("'); DROP TABLE assets;--", "image")
        self.assertEqual(rights_report()["count"], 1)


if __name__ == "__main__":
    unittest.main()
