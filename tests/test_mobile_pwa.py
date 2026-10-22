"""Mobile PWA session, flow, and the unchanged MCP gate."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

os.environ.setdefault("ALDOL_DESIGN_MCP_KEY", "mobile-test-key-" + ("k" * 32))
import app  # noqa: E402
from mobile_pwa import auth  # noqa: E402

KEY = os.environ["ALDOL_DESIGN_MCP_KEY"]


def brief():
    return {
        "preset": "slate",
        "goal": "원정 현황",
        "components": [{
            "name": "Energy",
            "role": "현재 에너지를 보여 주는 상태 카드",
            "states": ["default"],
            "mobile_behavior": "390px에서는 최상단에 둔다",
            "interaction": "호스트에서 값을 갱신",
            "accessibility": "수치와 단위를 함께 제공한다",
        }],
    }


class MobilePwaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_cm = TestClient(app.app)
        cls.client = cls._client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_cm.__exit__(None, None, None)

    def setUp(self):
        os.environ["ALDOL_DESIGN_MCP_KEY"] = KEY
        self.client.cookies.clear()

    def test_static_shell_has_no_secret_storage(self):
        page = self.client.get("/mobile/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("별도 모바일 웹", page.text)
        self.assertIn("NOT_IMPLEMENTED", page.text)
        self.assertIn('sandbox', page.text)
        self.assertNotIn(KEY, page.text)
        script = self.client.get("/mobile/app.js").text
        worker = self.client.get("/mobile/sw.js").text
        for source in (script, worker, page.text):
            self.assertNotIn("localStorage", source)
            self.assertNotIn("sessionStorage", source)
            self.assertNotIn(KEY, source)
        self.assertEqual(self.client.get("/mobile/manifest.webmanifest").status_code, 200)
        self.assertEqual(self.client.get("/mobile/icon-192.png").status_code, 200)
        self.assertEqual(self.client.get("/mobile").status_code, 200)

    def test_session_cookie_is_http_only_and_wrong_key_is_rejected(self):
        wrong = self.client.post("/mobile/api/session", json={"key": "not-the-key"})
        self.assertEqual(wrong.status_code, 401)
        self.assertNotIn(KEY, wrong.text)
        login = self.client.post("/mobile/api/session", json={"key": KEY})
        self.assertEqual(login.status_code, 200)
        cookie = login.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=strict", cookie)
        self.assertNotIn(KEY.lower(), cookie)
        self.assertNotIn(KEY, login.text)
        status = self.client.get("/mobile/api/session").json()
        self.assertTrue(status["authenticated"])
        self.assertTrue(status["configured"])

    def test_cross_site_request_is_rejected(self):
        response = self.client.post(
            "/mobile/api/session",
            headers={"origin": "https://evil.example", "sec-fetch-site": "cross-site"},
            json={"key": KEY},
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(KEY, response.text)

    def test_flow_reports_placeholders_and_strips_script(self):
        self.assertEqual(self.client.post("/mobile/api/flow", json=brief()).status_code, 401)
        self.client.post("/mobile/api/session", json={"key": KEY})
        response = self.client.post("/mobile/api/flow", json=brief())
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual([step["tool"] for step in body["steps"]],
                         ["generate_design_spec", "ui_import_bonsae", "ui_generate"])
        self.assertFalse(body["handoff"]["functional_ui_complete"])
        self.assertFalse(body["handoff"]["release_authorized"])
        self.assertEqual(body["handoff"]["unimplemented"]["components"][0]["implementation"], "NOT_IMPLEMENTED")
        self.assertIn("loading", body["constraints"]["state_gaps"][0]["missing_states"])
        self.assertNotIn("<script", body["preview_html"].lower())
        self.assertIn("Energy", body["preview_html"])
        self.assertNotIn(KEY, response.text)
        self.assertFalse(body["android_device_verified"])

    def test_unsafe_component_text_stays_escaped(self):
        self.client.post("/mobile/api/session", json={"key": KEY})
        payload = brief()
        payload["components"][0]["name"] = "<img src=x onerror=alert(1)>"
        response = self.client.post("/mobile/api/flow", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        preview = response.json()["preview_html"]
        self.assertIn("&lt;img", preview)
        self.assertNotIn("<img src=x", preview)

    def test_invalid_brief_names_the_step(self):
        self.client.post("/mobile/api/session", json={"key": KEY})
        response = self.client.post("/mobile/api/flow", json={"goal": "", "components": []})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["step"], "generate_design_spec")
        self.assertNotIn(KEY, response.text)

    def test_tool_catalog_marks_the_three_call_path(self):
        self.client.post("/mobile/api/session", json={"key": KEY})
        catalog = self.client.get("/mobile/api/tools")
        self.assertEqual(catalog.status_code, 200)
        body = catalog.json()
        bonsae = {item["name"]: item["callable_from_pwa"] for item in body["servers"]["bonsae"]}
        ui = {item["name"]: item["callable_from_pwa"] for item in body["servers"]["ui"]}
        self.assertEqual(set(bonsae), {"analyze_design", "generate_design_spec", "review_visual"})
        self.assertEqual(set(ui), {
            "ui_catalog", "ui_validate", "ui_audit", "ui_review", "ui_review_markup",
            "ui_generate", "ui_presets", "ui_import_bonsae",
        })
        self.assertTrue(bonsae["generate_design_spec"])
        self.assertFalse(bonsae["review_visual"])
        self.assertTrue(ui["ui_import_bonsae"])
        self.assertTrue(ui["ui_generate"])
        self.assertFalse(ui["ui_review"])

    def test_existing_mcp_gate_is_unchanged(self):
        anonymous = self.client.post("/ui/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(anonymous.status_code, 401)
        blocked = self.client.post(
            "/bonsae/mcp",
            headers={"authorization": "Bearer " + KEY, "origin": "https://mobile.example"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        self.assertEqual(blocked.status_code, 403)
        self.assertEqual(self.client.get("/health").json()["status"], "ok")
        self.assertEqual(self.client.get("/mobile/nope").status_code, 404)

    def test_short_key_keeps_mcp_closed_and_blocks_the_session(self):
        os.environ["ALDOL_DESIGN_MCP_KEY"] = "short"
        try:
            self.assertFalse(auth.configured())
            self.assertEqual(self.client.get("/mobile/").status_code, 200)
            self.assertEqual(self.client.post("/mobile/api/session", json={"key": "short"}).status_code, 503)
            self.assertEqual(self.client.post("/ui/mcp").status_code, 503)
            self.assertNotIn("short", self.client.get("/mobile/app.js").text)
        finally:
            os.environ["ALDOL_DESIGN_MCP_KEY"] = KEY

    def test_logout_ends_the_session(self):
        self.client.post("/mobile/api/session", json={"key": KEY})
        self.assertEqual(self.client.delete("/mobile/api/session").status_code, 200)
        self.assertFalse(self.client.get("/mobile/api/session").json()["authenticated"])
        self.assertEqual(self.client.post("/mobile/api/flow", json=brief()).status_code, 401)


if __name__ == "__main__":
    unittest.main()
