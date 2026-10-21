"""Anti-slop quality-gate regression: explainability, intentional styles, old format."""
import json
from pathlib import Path
import unittest
from ui_core import core

HERE = Path(__file__).resolve().parents[1]


def example(which="web-dashboard"):
    return json.loads((HERE / "examples" / f"{which}.json").read_text(encoding="utf-8"))


def serialized(doc):
    return json.dumps(doc, ensure_ascii=False)


class AntiSlopTests(unittest.TestCase):
    def test_clean_web_and_game_have_no_findings(self):
        for kind in ("web-dashboard", "expedition-hud-v03"):
            with self.subTest(kind=kind):
                review = core.review(serialized(example(kind)))
                self.assertEqual(review["status"], "clear")
                self.assertEqual(review["findings"], [])
                self.assertTrue(review["human_review_required"])

    def test_heading_cliche_is_high(self):
        d = example()
        d["root"]["children"][1]["text"] = "한곳에서 모든 새로운 경험"
        issues = core.review(serialized(d))["findings"]
        self.assertTrue(any(f["rule"] == "generic-headline" and f["severity"] == "high" for f in issues))

    def test_explainable_paths_suggestions(self):
        d = example()
        d["root"]["children"][1]["text"] = "한곳에서 모든 화면 관리"
        issue = next(f for f in core.review(serialized(d))["findings"] if f["rule"] == "generic-headline")
        self.assertIn("children[1]", issue["path"])
        self.assertIn("실제 목적", issue["suggestion"])
        self.assertTrue(issue["evidence"])

    def test_plain_emoji_button_is_flagged_not_blocked(self):
        d = example("expedition-hud-v03")
        d["root"]["children"][1]["children"][1]["children"][0]["label"] = "✦ 전술"
        self.assertTrue(any(f["rule"] == "ornamental-glyph" for f in core.review(serialized(d))["findings"]))
        # The medium-severity style heuristic is advisory, even in enforce mode.
        self.assertIn("html", core.render(serialized(d), "game-hud-html", "enforce"))

    def test_many_repeated_metric_cards(self):
        d = example()
        cards = d["root"]["children"][3]["children"]
        cards[:] = [cards[0]] * 4
        report = core.review(serialized(d))
        self.assertIn("repeated-metric-cards", [x["rule"] for x in report["findings"]])

    def test_data_mode_missing_is_high(self):
        d = example()
        del d["data_mode"]
        self.assertIn("no-data-provenance", [x["rule"] for x in core.review(serialized(d))["findings"]])
        with self.assertRaisesRegex(ValueError, "quality gate"):
            core.render(serialized(d), quality_mode="enforce")
        self.assertIn("html", core.render(serialized(d), quality_mode="advisory"))

    def test_waiver_requires_traceable_reason(self):
        d = example()
        d["root"]["children"][1]["text"] = "한곳에서 모든 화면"
        d["design"]["exceptions"] = [{"rule": "generic-headline", "reason": "고유 시리즈 문구로서 이미 사용자 테스트를 거쳤기 때문"}]
        report = core.review(serialized(d))
        self.assertEqual(report["findings"], [])
        self.assertEqual(len(report["waived"]), 1)
        self.assertIn("사용자 테스트", report["waived"][0]["waiver_reason"])
        self.assertIn("html", core.render(serialized(d), quality_mode="enforce"))

    def test_invalid_waiver_rejected(self):
        d = example()
        d["design"]["exceptions"] = [{"rule": "generic-headline", "reason": "그냥"}]
        self.assertFalse(core.validate(serialized(d))["valid"])
        d["design"]["exceptions"] = [{"rule": "ignore-everything", "reason": "명시적으로 예외를 적용한 사유입니다"}]
        self.assertFalse(core.validate(serialized(d))["valid"])

    def test_unknown_design_rejected(self):
        d = example()
        d["design"]["css"] = "background: url(javascript:evil())"
        self.assertFalse(core.validate(serialized(d))["valid"])

    def test_invalid_data_mode_rejected(self):
        d = example()
        d["data_mode"] = "real_verified"
        self.assertFalse(core.validate(serialized(d))["valid"])

    def test_high_priority_inactive_action(self):
        d = example()
        del d["root"]["children"][4]["children"][0]["children"][-1]["action"]
        self.assertTrue(any(f["rule"] == "inactive-button" for f in core.review(serialized(d))["findings"]))

    def test_audit_exposes_anti_slop(self):
        review = core.audit(serialized(example()))["anti_slop"]
        self.assertEqual(review["status"], "clear")
        self.assertIn("human_review_required", review)

    def test_render_and_react_have_same_review(self):
        source=serialized(example())
        web=core.render(source,"web-html")
        react=core.render(source,"react-tsx")
        self.assertEqual(web["anti_slop"], react["anti_slop"])

    def test_css_less_default_decoration_and_accessibility(self):
        css=core.render(serialized(example()))["css"]
        self.assertNotIn("backdrop-filter", css)
        self.assertNotIn("linear-gradient", css)
        self.assertIn("min-height:48px",css)
        self.assertIn("prefers-reduced-motion",css)

    def test_demo_provenance_in_markup(self):
        self.assertIn('data-alui-data-mode="demo"',core.render(serialized(example()))["html"])

    def test_unapproved_quality_mode_rejected(self):
        with self.assertRaisesRegex(ValueError, "quality_mode"):
            core.render(serialized(example()), quality_mode="silence_all")

    def test_catalog_documents_gate(self):
        catalog = core.catalog()
        self.assertEqual(catalog["quality_patch"], "0.3.2")
        self.assertIn("ui_review",str(catalog["anti_slop"]))

if __name__ == "__main__":
    unittest.main()
