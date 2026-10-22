"""BONSAE -> UI MCP handoff: deterministic, loss-aware and fail-closed."""
import json
import unittest

from ui_core import core
from ui_core.bonsae_bridge import import_bonsae


def bonsae_response():
    spec = {
        "goal": "원정 현황",
        "device": "responsive",
        "tokens": {"primary": "#E9B35E", "background": "#172638",
                   "foreground": "#F7F9FF", "density": "compact",
                   "--bespoke-shadow": "brand-only"},
        "components": [
            {"name": "Energy", "role": "현재 에너지를 보여 주는 상태 카드",
             "states": ["default", "loading", "error"],
             "mobile_behavior": "390px에서는 최상단에 항상 보이도록 배치",
             "interaction": "호스트에서 실시간 에너지 갱신",
             "accessibility": "수치와 단위 함께 제공"},
            {"name": "Start", "role": "원정 시작 액션",
             "states": ["default", "disabled"],
             "mobile_behavior": "터치 가능한 크기 유지",
             "interaction": "호스트에서 원정 시작 이벤트 처리"},
        ],
        "layouts": {"390": "단일 열", "820": "두 열", "1280": "세 열"},
        "motion": "reduced-motion 존중",
        "accessibility": "버튼 키보드 포커스",
        "visual_verification": "NOT_RUN",
        "source": "user intent",
        "layout_defaults_proposed": False,
        "seum_handoff": {"critical_states": "Preserve all states"},
    }
    return json.dumps({"specification": json.dumps(spec, ensure_ascii=False),
                       "constraints": json.dumps({"release_authorized": False})},
                      ensure_ascii=False)


class BonsaeBridgeTests(unittest.TestCase):
    def test_real_bonsae_response_shape_is_accepted(self):
        r = import_bonsae(bonsae_response())
        self.assertEqual(r["status"], "HANDOFF_REVIEW_REQUIRED")
        self.assertTrue(r["ui_validation"]["valid"])
        self.assertEqual(r["mapped"]["component_placeholders"], 2)
        self.assertEqual(r["unmapped_tokens"], ["--bespoke-shadow"])
        self.assertFalse(r["functional_ui_complete"])
        self.assertFalse(r["release_authorized"])
        self.assertTrue(r["human_review_required"])
        self.assertEqual(r["unimplemented"]["components"][0]["states"],
                         ["default", "loading", "error"])
        self.assertEqual(r["unimplemented"]["layouts"]["390"], "단일 열")

    def test_preview_renders_but_never_invents_game_actions(self):
        r = import_bonsae(bonsae_response(), "slate")
        doc = json.loads(r["ui_spec_json"])
        self.assertEqual(doc["preset"], "slate")
        self.assertEqual(doc["theme"]["primary"], "#E9B35E")
        self.assertEqual(doc["tokens"]["density"], "compact")
        self.assertEqual(doc["root"]["children"][1]["type"], "card")
        self.assertEqual(core.audit(r["ui_spec_json"])["button_count"], 0)
        self.assertTrue(core.render(r["ui_spec_json"])["html"])
        self.assertNotIn('"action"', r["ui_spec_json"])

    def test_long_goal_truncation_is_reported_not_hidden(self):
        data = json.loads(bonsae_response())
        spec = json.loads(data["specification"])
        spec["goal"] = "가" * 120
        data["specification"] = json.dumps(spec)
        r = import_bonsae(json.dumps(data))
        self.assertEqual(len(json.loads(r["ui_spec_json"])["title"]), 100)
        self.assertIsNotNone(r["unimplemented"]["goal_overflow"])

    def test_reject_invalid_tokens_and_shapes(self):
        base = json.loads(bonsae_response())
        for field, bad in (("primary", "url(http://example.test)"),
                           ("density", "giant")):
            with self.subTest(field=field):
                data = json.loads(base["specification"])
                data["tokens"][field] = bad
                with self.assertRaises(ValueError):
                    import_bonsae(json.dumps(data))
        for invalid in ("null", "[]", "{", "{}", '"free text"'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                import_bonsae(invalid)

    def test_reject_unknown_fields_and_duplicate_components(self):
        data = json.loads(bonsae_response())
        spec = json.loads(data["specification"])
        spec["command"] = "execute"
        with self.assertRaises(ValueError):
            import_bonsae(json.dumps(spec))
        del spec["command"]
        spec["components"].append(spec["components"][0])
        with self.assertRaises(ValueError):
            import_bonsae(json.dumps(spec))

    def test_html_like_content_is_escaped_by_ui_core(self):
        data = json.loads(bonsae_response())
        spec = json.loads(data["specification"])
        spec["components"][0]["name"] = "<img src=x onerror=alert(1)>"
        r = import_bonsae(json.dumps(spec))
        html = core.render(r["ui_spec_json"])["html"]
        self.assertIn("&lt;img", html)
        self.assertNotIn("<img src=x", html)

    def test_legacy_ui_contract_unchanged(self):
        old = '{"version":"0.1","title":"테스트","root":{"type":"button","label":"확인"}}'
        self.assertTrue(core.validate(old)["valid"])


if __name__ == "__main__":
    unittest.main()
