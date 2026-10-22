"""Chromium phone-width checks. This is not a physical Android device test."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path("/opt/cursor/artifacts/mobile-pwa")
KEY = "local-browser-key-" + ("b" * 32)
ANDROID = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
)


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait(port):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(100):
        try:
            if opener.open(f"http://127.0.0.1:{port}/health", timeout=1).status == 200:
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("browser target did not become ready")


def main():
    port = _port()
    OUT.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "ALDOL_DESIGN_MCP_KEY": KEY, "NO_PROXY": "127.0.0.1,localhost"}
    log_path = OUT / "server.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
            cwd=ROOT, env=env, stdout=log, stderr=log,
        )
        try:
            _wait(port)
            results = []
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                for width in (360, 390):
                    context = browser.new_context(
                        viewport={"width": width, "height": 800},
                        is_mobile=True,
                        has_touch=True,
                        device_scale_factor=2,
                        user_agent=ANDROID,
                    )
                    page = context.new_page()
                    page.goto(f"http://127.0.0.1:{port}/mobile/", wait_until="networkidle")
                    page.get_by_text("아직 생성 결과가 없습니다.").wait_for()
                    page.screenshot(path=str(OUT / f"empty-{width}.png"))
                    page.locator("#key").fill(KEY)
                    page.locator("#login-form button").click()
                    page.locator("#composer").wait_for()
                    assert KEY not in page.content()
                    assert KEY not in page.evaluate("document.cookie")
                    page.locator("#example").click()
                    page.locator("#goal").fill("")
                    page.locator("#run").click()
                    page.locator("#error").wait_for()
                    assert "거절" in page.locator("#error").inner_text()
                    page.screenshot(path=str(OUT / f"error-{width}.png"))
                    page.locator("#example").click()
                    page.locator("#run").click()
                    page.locator("#gap-title").wait_for()
                    assert "NOT_IMPLEMENTED" in page.locator("#result").inner_text()
                    frame = page.frame_locator("#preview")
                    frame.get_by_text("Energy").wait_for()
                    overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                    heights = page.eval_on_selector_all(
                        "button",
                        "els => els.filter(el => el.getClientRects().length).map(el => el.getBoundingClientRect().height)",
                    )
                    assert overflow <= 1, (width, overflow)
                    assert heights and min(heights) >= 44, (width, heights)
                    page.locator("#result").scroll_into_view_if_needed()
                    page.screenshot(path=str(OUT / f"result-{width}.png"), full_page=True)
                    context.set_offline(True)
                    page.locator("#run").click()
                    page.locator("#offline").wait_for()
                    assert "오프라인" in page.locator("#error").inner_text()
                    page.screenshot(path=str(OUT / f"offline-{width}.png"))
                    context.set_offline(False)
                    context.close()
                    results.append({
                        "viewport": width,
                        "status": "PASS",
                        "browser": "Chromium mobile emulation",
                        "physical_android_device": False,
                        "min_touch_height": min(heights),
                        "horizontal_overflow": overflow,
                    })
                browser.close()
        finally:
            process.terminate()
            process.wait(timeout=10)
    log_text = log_path.read_text(errors="replace")
    if KEY in log_text:
        raise RuntimeError("browser server log contains the test key")
    log_path.unlink()
    print(json.dumps({"results": results, "passed": len(results)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
