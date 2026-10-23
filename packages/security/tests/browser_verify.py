"""Chromium mobile emulation against real loopback HTTP; synthetic data only.

No cloud requests, raw network traces, tokens, or console messages are saved.
Screenshots (optional) are taken only after clearing the synthetic token field.
"""
import json
import os
from pathlib import Path
import threading
from unittest.mock import patch

from playwright.sync_api import sync_playwright, expect
from test_http_integration import TestLoopbackHTTP, FAKE_TOKEN, FAKE_VALUE
import http_api

VIEWPORTS = [(360, 800), (390, 844), (412, 915), (667, 375)]


def main():
    TestLoopbackHTTP.setUpClass()
    try:
        origin = 'http://127.0.0.1:' + str(TestLoopbackHTTP.port)
        root = TestLoopbackHTTP.root
        baseline = {p.name: (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns)
                    for p in root.iterdir()}
        results = []
        with sync_playwright() as playwright:
            options = {'headless': True}
            if os.getenv('ALDOL_TEST_CHROMIUM'):
                options['executable_path'] = os.environ['ALDOL_TEST_CHROMIUM']
            browser = playwright.chromium.launch(**options)
            for width, height in VIEWPORTS:
                context = browser.new_context(viewport={'width': width, 'height': height},
                                              is_mobile=True, has_touch=True)
                page = context.new_page()
                errors, console, urls, requests = [], [], [], []
                page.on('pageerror', lambda _: errors.append(True))
                page.on('console', lambda msg: console.append(msg.text))
                page.on('request', lambda req: urls.append(req.url))
                page.on('request', lambda req: requests.append(req.method) if req.url.endswith('/api/scan') else None)
                page.goto(origin)
                page.locator('#tool').select_option('guardian')
                assert page.locator('#tool').input_value() == 'guardian'
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                for selector in ('#token', '#path', '#tool', '#scan'):
                    box = page.locator(selector).bounding_box()
                    assert box['height'] >= 48 and box['width'] >= 48
                page.locator('#scan').click()
                assert page.locator('#state').inner_text() == '토큰이 필요합니다'
                page.locator('#token').fill(FAKE_TOKEN)

                original = http_api.guardian_report
                entered, release = threading.Event(), threading.Event()
                def delayed(subpath):
                    entered.set()
                    if not release.wait(5):
                        raise RuntimeError('synthetic timeout')
                    return original(subpath)
                with patch('http_api.guardian_report', side_effect=delayed):
                    count = len(requests)
                    page.locator('#scan').click()
                    try:
                        assert entered.wait(2)
                        assert page.locator('#scan').is_disabled()
                        page.evaluate("document.querySelector('#scan').dispatchEvent(new Event('click'))")
                        assert len(requests) == count + 1
                    finally:
                        release.set()
                    expect(page.locator("#scan")).to_be_enabled()
                result = json.loads(page.locator('#output').inner_text())
                assert result['credential_count'] == 2
                assert result['status'] == 'INVENTORIED'
                assert baseline == {p.name: (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns)
                                    for p in root.iterdir()}
                assert all(value not in page.locator('#output').inner_text()
                           for value in (FAKE_TOKEN, FAKE_VALUE, str(root), 'OPENAI_API_KEY'))

                def scan():
                    page.locator('#scan').click()
                    expect(page.locator("#scan")).to_be_enabled()
                page.locator('#token').fill('incorrect-synthetic-token')
                scan()
                assert page.locator('#state').inner_text() == '인증 실패 (401)'
                # Reverse proxies may return HTML for 401; still an auth failure.
                def html_denial(handler, code, result):
                    handler._headers(401, 'text/html; charset=utf-8')
                    handler.wfile.write(b'<html>synthetic auth denial</html>')
                with patch.object(http_api.Handler, '_send', html_denial):
                    scan()
                    assert page.locator('#state').inner_text() == '인증 실패 (401)'
                assert 'synthetic auth denial' not in page.locator('#output').inner_text()
                page.locator('#token').fill(FAKE_TOKEN)
                context.set_offline(True)
                scan()
                assert page.locator('#state').inner_text() == '연결 실패'
                context.set_offline(False)
                page.locator('#path').fill('../')
                scan()
                assert page.locator('#state').inner_text().startswith('BLOCKED')
                assert '안전 판정 아님' in page.locator('#state').inner_text()
                page.locator('#path').fill('.')
                # Deliberate fixture changes, distinct from read-only scan invariance.
                for p in root.iterdir():
                    p.unlink()
                scan()
                assert page.locator('#state').inner_text().startswith('UNKNOWN')
                assert '안전 판정 아님' in page.locator('#state').inner_text()
                (root / 'secret-guardian.inventory.json').write_text('{')
                scan()
                assert page.locator('#state').inner_text().startswith('INCOMPLETE')
                assert '안전 판정 아님' in page.locator('#state').inner_text()
                (root / '.env').write_text('TOKEN=SYNTHETIC_BROWSER_ONLY\n')
                (root / '.env').chmod(0o644)
                scan()
                assert page.locator('#state').inner_text().startswith('FINDINGS_WITH_GAPS')
                assert '안전 판정 아님' in page.locator('#state').inner_text()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert page.evaluate('localStorage.length === 0 && sessionStorage.length === 0')
                assert not context.cookies()
                assert not errors
                assert all(url.startswith(origin + '/') for url in urls)
                assert all(FAKE_TOKEN not in url and FAKE_VALUE not in url for url in urls)
                assert all(FAKE_TOKEN not in msg and FAKE_VALUE not in msg for msg in console)
                page.locator('#token').fill('')
                output = os.getenv('ALDOL_TEST_BROWSER_OUTPUT')
                if output:
                    folder = Path(output)
                    folder.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(folder / f'mobile-{width}x{height}.png'), full_page=True)
                for name, (content, mode, mtime) in baseline.items():
                    path = root / name
                    path.write_bytes(content)
                    path.chmod(mode)
                    os.utime(path, ns=(mtime, mtime))
                results.append({'viewport': f'{width}x{height}', 'passed': True,
                                'overflow': False, 'touch_target_min_px': 48,
                                'real_loopback_http': True, 'storage_empty': True})
                context.close()
            browser.close()
        return {'passed': True, 'viewports': results, 'android_physical': 'NOT_VERIFIED',
                'remote_protected_qa': 'BLOCKED', 'external_requests': 0}
    finally:
        TestLoopbackHTTP.tearDownClass()


if __name__ == '__main__':
    print(json.dumps(main()))
