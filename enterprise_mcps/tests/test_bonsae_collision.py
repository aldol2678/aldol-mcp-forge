"""BONSAE P0 collision regression tests. Offline; no GitHub Actions required."""
import importlib.util
import json
import os
import shutil
import unittest
from unittest.mock import patch
from enterprise_mcps import bonsae

PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAGUlEQVR4nGNMmf2QgRTARJLqUQ2jGoaUBgDuHgIAeSnmhQAAAABJRU5ErkJggg=="

class CollisionVerdictTests(unittest.TestCase):
    def _fake(self, overlaps):
        return {"rendered": True, "viewports": [{"viewport": 390, "overflow": False, 
            "clippedContainers": [], "smallTouchTargets": [], "contrast": [], 
            "tokenDrift": [], "overlaps": overlaps, 
            "overlapCoverage": {"viewportOnly": True, "truncated": False}}]}

    def test_overlap_is_render_failure_not_pass(self):
        sample = [{"kind": "TEXT_MEDIA", "first": {"selector": "#title"}, 
                   "second": {"selector": "#image"}}]
        with patch("enterprise_mcps.bonsae_visual.render_html", return_value=self._fake(sample)):
            result = bonsae.review_visual(json.dumps({"artifact_id": "p0-overlap", "html": "<main>충돌</main>"}))
        self.assertEqual("FAIL_RENDER_CHECKS", result["verdict"])
        findings = json.loads(result["findings"])
        self.assertFalse(findings["whole_screen_pass"])
        self.assertIn("layout overlaps", [f["check"] for f in findings["render_check_failures"]])

    def test_clean_geometry_never_implies_whole_screen_pass(self):
        with patch("enterprise_mcps.bonsae_visual.render_html", return_value=self._fake([])):
            result = bonsae.review_visual(json.dumps({"artifact_id": "p0-clean", "html": "<main>정상</main>"}))
        self.assertEqual("HOLD_PARTIAL_VISUAL", result["verdict"])
        self.assertFalse(json.loads(result["findings"])["whole_screen_pass"])

    def test_unavailable_browser_stays_hold(self):
        with patch("enterprise_mcps.bonsae_visual.render_html", return_value={"rendered": False, "reason": "BROWSER_UNAVAILABLE"}):
            result = bonsae.review_visual(json.dumps({"artifact_id": "p0-no-browser", "html": "<main>검사</main>"}))
        self.assertEqual("HOLD_UNINSPECTED", result["verdict"])

class CollisionChromiumTests(unittest.TestCase):
    def test_real_browser_fixtures(self):
        if not importlib.util.find_spec("playwright"):
            self.skipTest("Playwright not installed")
        from playwright.sync_api import sync_playwright
        from enterprise_mcps.bonsae_visual import _MEASURE
        executable = os.environ.get("BONSAE_BROWSER_EXECUTABLE") or shutil.which("chromium") or shutil.which("chromium-browser")
        if not executable:
            self.skipTest("Chromium not installed")
        fixtures = {
            "text_media": ('<div style="position:relative;height:220px"><img id="image" src="'+PNG+'" style="position:absolute;top:0;left:0;width:260px;height:170px"><h1 id="title" style="position:absolute;top:20px;left:12px">제목 겹침</h1></div>', "TEXT_MEDIA"),
            "text_text": ('<div style="position:relative;height:220px"><h1 style="position:absolute;top:0">첫 번째 글씨</h1><p style="position:absolute;top:0">두 번째 글씨</p></div>', "TEXT_TEXT"),
            "clean": ('<section><h2>제목</h2><img src="'+PNG+'" width="72" height="40"><p>설명</p></section>', None),
            "intentional": ('<section data-bonsae-overlap="intentional" style="position:relative;height:180px"><img src="'+PNG+'" style="position:absolute;width:250px;height:160px"><h2 style="position:absolute;top:45px">의도된 배너</h2></section>', None),
            "intentional_text_clash": ('<section data-bonsae-overlap="intentional" style="position:relative;height:180px"><img src="'+PNG+'" style="position:absolute;width:250px;height:160px"><h2 style="position:absolute;top:45px">타이틀</h2><p style="position:absolute;top:45px">충돌 문구</p></section>', "TEXT_TEXT"),
            "hidden": ('<div><img src="'+PNG+'" width="100" height="100"><p style="display:none">숨긴 글씨</p></div>', None),
            "inline": ('<p>자연스러운 <strong>인라인</strong> 문장입니다.</p>', None),
        }
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=executable, headless=True, args=["--no-sandbox"])
            try:
                for width in (390, 820, 1280):
                    context = browser.new_context(viewport={"width": width, "height": 820}, java_script_enabled=False)
                    context.route("**/*", lambda route: route.abort())
                    page = context.new_page()
                    for name, (html, expected) in fixtures.items():
                        with self.subTest(width=width, fixture=name):
                            page.set_content('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:; script-src \'none\'">' + html)
                            result = page.evaluate(_MEASURE, {"tokens": {}})
                            kinds = {o["kind"] for o in result["overlaps"]}
                            if expected:
                                self.assertIn(expected, kinds)
                            else:
                                self.assertEqual(set(), kinds)
                            self.assertFalse(result["overlapCoverage"]["truncated"])
                    context.close()
            finally:
                browser.close()

if __name__ == "__main__":
    unittest.main(verbosity=2)
