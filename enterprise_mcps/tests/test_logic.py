"""Independent offline regression for nine real specialist handlers."""
import hashlib
import json
import unittest

from enterprise_mcps import seum, bonsae, majung
from enterprise_mcps.common import contract, verify_output
from enterprise_mcps.server import FUNCTIONS, invoke


def js(data):
    return json.dumps(data, ensure_ascii=False)


class CanonicalContractTests(unittest.TestCase):
    def test_exact_tool_inventory_and_output_contracts(self):
        for company, functions in FUNCTIONS.items():
            with self.subTest(company=company):
                declared = {x["name"] for x in contract(company)["tools"]}
                self.assertEqual(set(functions), declared)
                self.assertEqual(len(functions), 3)
        with self.assertRaises(ValueError):
            verify_output("seum", "analyze_code", {"summary": 42, "risks": "[]"})
        with self.assertRaisesRegex(ValueError, "Unknown"):
            invoke("seum", "unknown_tool", {})
        with self.assertRaisesRegex(ValueError, "Unknown tool input"):
            invoke("seum", "analyze_code", {"repository": "{}", "whoami": "bad"})

    def test_python_ast_detection_no_source_execution(self):
        source = 'def run():\n    eval("1+1")\n    return 3\n'
        r = invoke("seum", "analyze_code", {"repository": js({
            "path": "src/app.py", "language": "python", "content": source})})
        self.assertEqual(json.loads(r["summary"])["functions"], 1)
        self.assertTrue(json.loads(r["summary"])["parse_ok"])
        self.assertIn("DYNAMIC_EXECUTION", [x["code"] for x in json.loads(r["risks"])])
        invalid = seum.analyze_code(js({"path": "src/broken.py", "language": "python",
                                         "content": "def x(:\n  pass"}))
        self.assertFalse(json.loads(invalid["summary"])["parse_ok"])

    def test_json_parse_validation(self):
        valid = seum.analyze_code(js({"path": "a.json", "language": "json", "content": '{"ok":true}'}))
        self.assertTrue(json.loads(valid["summary"])["parse_ok"])
        broken = seum.analyze_code(js({"path": "a.json", "language": "json", "content": '{wrong}'}))
        self.assertEqual(json.loads(broken["risks"])[0]["code"], "JSON_SYNTAX")

    def test_checksum_guarded_diff_without_write(self):
        original = 'answer = 1\n'
        source = js({"path": "src/example.py", "content": original})
        change = js({"find": "answer = 1", "replace": "answer = 2",
                     "expected_sha256": hashlib.sha256(original.encode()).hexdigest()})
        result = invoke("seum", "implement_change", {"repository": source, "request": change})
        self.assertIn("+answer = 2", result["change_summary"])
        self.assertFalse(json.loads(result["verification"])["applied"])
        with self.assertRaisesRegex(ValueError, "STALE_SOURCE"):
            seum.implement_change(source, js({"find": "answer = 1",
                "replace": "answer = 2", "expected_sha256": "deadbeef"}))
        bad = js({"find": "answer = 1", "replace": "def bad(:",
                  "expected_sha256": hashlib.sha256(original.encode()).hexdigest()})
        with self.assertRaisesRegex(ValueError, "syntax check"):
            seum.implement_change(source, bad)

    def test_technical_release_gate_no_launch(self):
        r = seum.review_release(js({"revision": "commit123", "checks": {"ci": "PASS"}}))
        self.assertEqual(r["verdict"], "HOLD")
        all_pass = {x: "PASS" for x in ("ci", "tests", "security", "cost", "mobile")}
        r = seum.review_release(js({"revision": "commit123", "checks": all_pass}))
        self.assertEqual(r["verdict"], "PASS")
        self.assertFalse(json.loads(r["evidence"])["release_authorized"])
        all_pass["security"] = "FAIL"
        self.assertEqual(seum.review_release(js({"revision": "commit123",
            "checks": all_pass}))["verdict"], "FAIL")

    def test_html_semantics_and_anti_clipping(self):
        html = '<html><head></head><body><img src="x"><input id="search"><button></button></body></html>'
        result = bonsae.analyze_design(html, "body { overflow-x: hidden; }")
        codes = [x["code"] for x in json.loads(result["findings"])["issues"]]
        for expected in ("MISSING_LANG", "MISSING_VIEWPORT", "IMG_ALT",
                         "INPUT_LABEL", "BUTTON_NAME", "POTENTIAL_CLIPPING"):
            self.assertIn(expected, codes)
        self.assertFalse(json.loads(result["findings"])["rendered_visual_qa"])

    def test_design_spec_preserves_explicit_intent(self):
        brief = js({"goal": "Mobile game", "device": "phone",
                    "components": [{"name": "Action", "role": "primary button",
                        "states": ["default", "disabled"], "mobile_behavior": "sticky bottom"}]})
        result = bonsae.generate_design_spec(brief)
        self.assertEqual(json.loads(result["specification"])["components"][0]["mobile_behavior"], "sticky bottom")
        self.assertIn("error", json.loads(result["constraints"])["state_gaps"][0]["missing_states"])
        self.assertFalse(json.loads(result["constraints"])["verified_in_browser"])

    def test_visual_gate_never_fakes_pixel_inspection(self):
        r = bonsae.review_visual(js({"artifact_id": "a1", "viewport": "390px",
                                     "observations": [], "screenshot_refs": ["https://example.com/a.png"]}))
        self.assertEqual(r["verdict"], "HOLD_UNINSPECTED")
        self.assertFalse(json.loads(r["findings"])["visual_inspection_performed"])

    def test_sourced_market_evidence_no_fake_verification(self):
        r = majung.research_market(js({"question": "Can this sell?", "sources": [
            {"title": "Example survey", "url": "https://example.com/data",
             "observed_at": "2026-01-01", "claim": "Users expressed interest"}]}), "KR")
        self.assertEqual(json.loads(r["evidence"])["independent_domains"], 1)
        self.assertFalse(json.loads(r["evidence"])["source_content_verified"])
        self.assertTrue(json.loads(r["uncertainties"]))
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            majung.research_market(js({"question": "x", "sources": [
                {"title": "bad", "url": "http://localhost", "observed_at": "2026-01-01",
                 "claim": "bad"}]}))

    def test_competitor_price_math_and_currency_rejection(self):
        competitor = {"name": "Other", "price": 80, "currency": "USD",
                      "source_url": "https://example.com/other", "observed_at": "2026-01-01"}
        base = {"name": "Our game", "price": 100, "currency": "USD", "competitors": [competitor]}
        r = majung.analyze_competitors(js(base))
        self.assertEqual(json.loads(r["competitors"])["rows"][0]["delta_percent_vs_ours"], -20.0)
        self.assertEqual(json.loads(r["differentiation"])["type"], "price_position_only")
        base["competitors"][0]["currency"] = "KRW"
        with self.assertRaisesRegex(ValueError, "Mixed currencies"):
            majung.analyze_competitors(js(base))

    def test_business_economics_advisory_only(self):
        data = {"name": "Product", "price": 100, "variable_cost": 25,
                "acquisition_cost": 10, "expected_customers": 100, "evidence_urls": []}
        r = majung.evaluate_opportunity(js(data))
        self.assertEqual(r["recommendation"], "HOLD")
        risks = json.loads(r["risks"])
        self.assertEqual(risks["scenario"]["unit_contribution"], 65.0)
        self.assertEqual(risks["scenario"]["projected_pre_fixed_cost_contribution"], 6500.0)
        self.assertFalse(risks["launch_authorized"])
        data["variable_cost"] = 110
        self.assertEqual(majung.evaluate_opportunity(js(data))["recommendation"], "NO-GO")

if __name__ == "__main__":
    unittest.main(verbosity=2)
