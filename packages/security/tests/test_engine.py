"""Offline tests: mock engine results, NEVER claim real scanner validation."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"ALDOL_SECURITY_ROOT": self.tmp.name,
                                          "ALDOL_SECURITY_OSV_NETWORK": "0"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_path_inside(self):
        a, b = engine._scoped_path(".")
        self.assertEqual(a, b)

    def test_parent_traversal(self):
        with self.assertRaises(ValueError):
            engine._scoped_path("../")
        with self.assertRaises(ValueError):
            engine._scoped_path("/etc")

    def test_symlink_outside(self):
        (self.root / "escape").symlink_to("/etc")
        with self.assertRaises(ValueError):
            engine._scoped_path(".")

    def test_no_scanner_is_unknown(self):
        with patch("engine.shutil.which", return_value=None):
            result = engine.scan("trivy")
        self.assertEqual(result["status"], "UNKNOWN")

    def test_osv_requires_opt_in(self):
        result = engine.scan("osv")
        self.assertEqual(result["status"], "BLOCKED")

    def test_trivy_secret_redaction(self):
        secret = "PRIVATE_SUPER_SECRET_DO_NOT_LOG"
        data = {"Results": [{"Vulnerabilities": [{"VulnerabilityID": "CVE-2026-1234",
                                                  "Severity": "HIGH", "Title": secret}],
                             "Secrets": [{"Match": secret, "Code": {"Lines": secret}}],
                             "Misconfigurations": [{}]}]}
        out = engine._trivy_report(data)
        self.assertEqual(out["secret_matches"], 1)
        self.assertEqual(out["misconfigurations"], 1)
        self.assertEqual(out["vulnerabilities"]["HIGH"], 1)
        self.assertNotIn(secret, json.dumps(out))

    def test_syft_inventory(self):
        out = engine._syft_report({"components": [{}, {}]})
        self.assertEqual(out["component_count"], 2)
        self.assertEqual(out["status"], "INVENTORIED")

    def test_osv_aggregation(self):
        out = engine._osv_report({"results": [{"packages": [{"vulnerabilities": [
            {"id": "GHSA-foo"}, {"id": "OSV-2026-test"}]}]}]})
        self.assertEqual(out["vulnerability_matches"], 2)

    def test_all_preserves_unknown(self):
        with patch("engine.scan", side_effect=[
            {"status": "FINDINGS"}, {"status": "BLOCKED"}, {"status": "INVENTORIED"}]):
            self.assertEqual(engine.scan_all()["overall"], "FINDINGS_WITH_GAPS")

    def test_scanner_output_invalid_not_pass(self):
        with patch("engine.shutil.which", return_value="/usr/bin/trivy"), \
             patch("engine.subprocess.run") as run:
            # The temporary sink receives no JSON from the mocked process.
            run.return_value.returncode = 0
            out = engine.scan("trivy")
        self.assertEqual(out["status"], "UNKNOWN")

    def test_scanner_argument_no_shell(self):
        with patch("engine.shutil.which", return_value="/usr/bin/trivy"), \
             patch("engine.subprocess.run") as run:
            run.return_value.returncode = 2
            engine.scan("trivy")
            args = run.call_args.args[0]
            self.assertTrue(isinstance(args, list))
            self.assertEqual(args[0], "/usr/bin/trivy")
            self.assertFalse(run.call_args.kwargs.get("shell", False))


if __name__ == "__main__":
    unittest.main()
