"""Execute the actual BONSAE generate_design_spec implementation with UI MCP.

Runs against a pinned BONSAE git worktree, never a stub or invented sample result.
No remote services or secrets. Verifies contract conversion and rendered Chromium
at mobile/tablet/desktop. Does NOT claim ChatGPT plugin or Android device success.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui_core import bonsae_bridge, core

source_root = Path(os.environ["BONSAE_SOURCE_ROOT"]).resolve()
assert (source_root / "enterprise_mcps" / "bonsae.py").is_file(), source_root
sys.path.insert(0, str(source_root))
from enterprise_mcps import bonsae

brief = {
    "goal": "원정 상태와 행동 정보를 확인하는 모바일 대시보드",
    "device": "responsive",
    "tokens": {
        "primary": "#E9B35E",
        "background": "#172638",
        "foreground": "#F7F9FF",
        "density": "compact",
    },
    "components": [
        {
            "name": "에너지 현황",
            "role": "잔여 에너지 5 / 10을 표시하는 상태 정보",
            "states": ["default", "loading", "empty", "error"],
            "mobile_behavior": "390px에서 정보를 숨기지 않고 상단에 배치",
            "interaction": "실제 에너지 갱신은 게임 호스트가 제공",
            "accessibility": "숫자와 단위를 음성으로 읽을 수 있게 표시",
        },
        {
            "name": "원정 시작",
            "role": "원정 시작 동작을 요청하는 영역",
            "states": ["default", "disabled", "loading"],
            "mobile_behavior": "터치할 수 있는 크기와 명확한 간격을 확보",
            "interaction": "시작 버튼은 호스트 이벤트에 연결되어야 함",
            "accessibility": "키보드 조작, 포커스 및 명확한 이름 필요",
        },
    ],
    "layouts": {
        "390": "단일 열로 재배치하고 중요 정보 보존",
        "820": "이중 열 레이아웃은 공간이 충분할 때만",
        "1280": "읽기 쉬운 폭의 본문 유지",
    },
    "motion": "prefers-reduced-motion을 존중",
    "accessibility": "버튼 레이블, 키보드 포커스, 상태 알림을 검증",
}
# BONSAE actual function path, not a hard-coded handoff result.
raw_result = bonsae.generate_design_spec(json.dumps(brief, ensure_ascii=False))
assert set(raw_result) == {"specification", "constraints"}, raw_result
design = json.loads(raw_result["specification"])
assert design["components"][0]["states"] == brief["components"][0]["states"]
converted = bonsae_bridge.import_bonsae(json.dumps(raw_result, ensure_ascii=False), "forest")
assert converted["ui_validation"]["valid"] is True
assert converted["mapped"]["component_placeholders"] == 2
assert converted["release_authorized"] is False
assert converted["functional_ui_complete"] is False
assert converted["unimplemented"]["layouts"] == brief["layouts"]
assert converted["unimplemented"]["components"][1]["interaction"] == brief["components"][1]["interaction"]
ui_spec = converted["ui_spec_json"]
assert core.audit(ui_spec)["button_count"] == 0, "Unimplemented button should not be invented"
for target in ("web-html", "game-hud-html", "react-tsx"):
    result = core.render(ui_spec, target, quality_mode="advisory")
    assert result.get("html") or result.get("component_tsx"), target
web = core.render(ui_spec, "web-html", quality_mode="advisory")
html = web["preview_html"]
assert "에너지 현황" in html and "원정 시작" in html

browser_results = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.getenv('CHROMIUM_EXECUTABLE', p.chromium.executable_path),
                                headless=True, args=["--no-sandbox"])
    for width in (390, 820, 1280):
        page = browser.new_page(viewport={"width": width, "height": 840}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.set_content(html, wait_until="load")
        report = page.evaluate("""() => ({
          width: document.documentElement.scrollWidth,
          viewport: innerWidth,
          cardCount: document.querySelectorAll('.alui-card').length,
          headings: [...document.querySelectorAll('.alui-text')].map(e => e.textContent.trim())
        })""")
        assert report["width"] <= report["viewport"] + 1, (width, report)
        assert report["cardCount"] == 2, (width, report)
        assert not errors, (width, errors)
        browser_results.append({"width": width, "overflow": False,
                                "cards": report["cardCount"], "page_errors": 0})
        page.close()
    browser.close()

print(json.dumps({
    "status": "PASS",
    "source": "actual BONSAE source at pinned git commit",
    "pipeline": [
        "bonsae.generate_design_spec",
        "ui_core.bonsae_bridge.import_bonsae",
        "ui_core.validate",
        "ui_core.render",
        "Chromium set_content viewport check",
    ],
    "outputs": ["web-html", "game-hud-html", "react-tsx"],
    "browser": browser_results,
    "live_remote_calls": False,
    "android_device_tested": False,
    "ui_functional_acceptance": False,
    "release_authorized": False,
}, ensure_ascii=False, indent=2))
