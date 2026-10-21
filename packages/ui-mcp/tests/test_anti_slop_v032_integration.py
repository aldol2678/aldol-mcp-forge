"""Regression tests for integration into existing ALDOL UI MCP core."""
import json
from pathlib import Path
import unittest
from ui_core import core

ROOT = Path(__file__).resolve().parents[1]
def load():
    return json.loads((ROOT / "examples/web-dashboard.json").read_text(encoding="utf-8"))
def write(doc):
    return json.dumps(doc, ensure_ascii=False)

class Integration(unittest.TestCase):
    def test_catalog_documents_new_tools_and_rules(self):
        c=core.catalog()
        self.assertEqual(c["quality_patch"], "0.3.2")
        self.assertIn("ui_review_markup", str(c["anti_slop"]))
        self.assertIn("decorative-accent-rail", c["anti_slop"]["rules"])
        self.assertIn("sloganized-declarative-headline", c["anti_slop"]["rules"])

    def test_declared_headline_found_and_enforced(self):
        d=load()
        d["root"]["children"][1]["text"] = "아이콘은 상태를 말한다."
        report=core.review(write(d))
        issue=next(x for x in report["findings"] if x["rule"] == "sloganized-declarative-headline")
        self.assertEqual(issue["severity"], "high")
        with self.assertRaisesRegex(ValueError, "quality gate"):
            core.render(write(d), quality_mode="enforce")
        self.assertIn("html", core.render(write(d), quality_mode="advisory"))

    def test_reasoned_exception_allows_enforced_render(self):
        d=load();d["root"]["children"][1]["text"] = "아이콘은 상태를 말한다."
        d["design"]["exceptions"]=[{
            "rule":"sloganized-declarative-headline",
            "reason":"브랜드 편집 캠페인에서 사전 검토한 의도적 제목"}]
        self.assertTrue(core.validate(write(d))["valid"])
        review=core.review(write(d))
        self.assertNotIn("sloganized-declarative-headline", [x["rule"] for x in review["findings"]])
        self.assertTrue(any(x["rule"]=="sloganized-declarative-headline" for x in review["waived"]))
        self.assertIn("html", core.render(write(d), quality_mode="enforce"))

    def test_functional_headings_not_flagged(self):
        d=load();d["root"]["children"][1]["text"]="저장 내역과 다운로드"
        self.assertFalse(any(x["rule"]=="sloganized-declarative-headline" for x in core.review(write(d))["findings"]))

    def test_html_multiple_rails_high(self):
        html="""<style>.card{border-left:3px solid lime}.notice{border-left:4px solid gold}</style>
        <h1>아이콘은 상태를 말한다.</h1>"""
        issues=core.review_markup(html)["findings"]
        self.assertEqual(len([x for x in issues if x["rule"]=="decorative-accent-rail"]),2)
        self.assertTrue(all(x["severity"]=="high" for x in issues))
        self.assertTrue(any(x["rule"]=="sloganized-declarative-headline" for x in issues))

    def test_html_reasons_and_invalid_input(self):
        src='<style>.step{border-left:2px solid red}</style>'
        waived=core.review_markup(src, json.dumps([{
           "rule":"decorative-accent-rail",
           "reason":"시간순 진행 단계의 현재 위치 표시를 위한 선"}],ensure_ascii=False))
        self.assertEqual(waived["findings"],[])
        self.assertEqual(len(waived["waived"]),1)
        self.assertIn("waiver_reason", waived["waived"][0])
        for exceptions in ('[{}]', '[{"rule":"does-not-exist", "reason":"정확하지 않은 예외입니다"}]'):
            with self.assertRaises(ValueError): core.review_markup(src, exceptions)
        with self.assertRaises(ValueError): core.review_markup('x'*120001)

    def test_generated_css_no_decorative_rail(self):
        for target in ('web-html','game-hud-html','react-tsx'):
            with self.subTest(target=target):
                generated=core.render(write(load()),target,quality_mode='enforce')
                self.assertNotIn('border-left:3px',generated['css'])
                if target != 'react-tsx':
                    report=core.review_markup(generated['preview_html'])
                    self.assertFalse(any(x['rule']=='decorative-accent-rail' for x in report['findings']))

    def test_old_versions_still_render(self):
        for old_version in ('0.1','0.2','0.3'):
            doc={'version':old_version,'title':'앱 탐색','root':{'type':'stack','children':[{'type':'button','label':'저장'}]}}
            self.assertIn('html',core.render(write(doc)))

    def test_render_and_review_react_match(self):
        d=load();d['root']['children'][1]['text']='아이콘은 상태를 말한다.'
        s=write(d)
        self.assertEqual(core.render(s,'react-tsx')['anti_slop'], core.review(s))
