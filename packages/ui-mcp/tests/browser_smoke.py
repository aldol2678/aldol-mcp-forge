"""Optional Chromium Playwright E2E for generated preview; no external network."""
from pathlib import Path
import json
import shutil
from playwright.sync_api import sync_playwright

base=Path(__file__).resolve().parents[1]
html_content=(base/'examples/game-hud-preview.html').read_text(encoding='utf-8')
results=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=shutil.which('chromium') or shutil.which('google-chrome'), headless=True, args=['--no-sandbox'])
    for width,height in [(360,740),(390,844),(768,1024),(1280,800)]:
        page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1, is_mobile=(width<500),has_touch=(width<500))
        page.set_default_timeout(3500)
        print('Viewport',width,flush=True)
        errs=[]
        page.on('pageerror', lambda e: errs.append(str(e)))
        page.set_content(html_content,wait_until='load')
        page.wait_for_timeout(50)
        page.screenshot(path=str(base/'examples'/f'game-hud-initial-{width}.png'),full_page=True)
        pre=page.evaluate('''() => ({viewport:innerWidth, scroll:document.documentElement.scrollWidth,
          top:document.querySelector('.alui-hud-overlay>.alui-stack>.alui-panel:first-child').getBoundingClientRect().toJSON(),
          bottom:document.querySelector('.alui-hud-overlay>.alui-stack>.alui-panel:last-child').getBoundingClientRect().toJSON(),
          buttons:[...document.querySelectorAll('button')].map(e=>({label:e.textContent,rect:e.getBoundingClientRect().toJSON()}))})''')
        assert pre['scroll'] <= pre['viewport']+1, (width,pre)
        assert pre['bottom']['bottom'] <= height+1, (width,pre)
        assert pre['top']['bottom']+20 < pre['bottom']['top'],(width,pre)
        for b in pre['buttons'][:2]:
            assert b['rect']['height']>=44 and b['rect']['width']>=44, (width,b)
        page.get_by_role('button',name='⚔ 전술').click()
        assert page.locator('[data-alui-id="tactics"]').is_visible()
        assert page.get_by_role('button',name='⚔ 전술').get_attribute('aria-expanded') == 'true'
        assert page.get_by_text('패널 열림').is_visible()
        page.get_by_role('button',name='반격 요청').click()
        assert 'battle:counter' in page.locator('.alui-demo-toast').inner_text()
        page.get_by_role('button',name='✦ 상태이상').click()
        assert page.locator('[data-alui-id="conditions"]').is_visible()
        assert not page.locator('[data-alui-id="tactics"]').is_visible()
        assert page.get_by_role('button',name='⚔ 전술').get_attribute('aria-expanded') == 'false'
        page.keyboard.press('Escape')
        assert not page.locator('[data-alui-id="conditions"]').is_visible()
        assert not errs, (width,errs)
        # restored default for screenshot and capture both states
        name=f'game-hud-{width}.png'
        page.screenshot(path=str(base/'examples'/name),full_page=True)
        results.append({'width':width,'height':height,'horizontal_overflow':False,'buttons_tested':2,
                        'toggle_click':'PASS','emit_event':'PASS','exclusive_panel':'PASS','escape':'PASS',
                        'no_page_errors':True,'screenshot':name, 'initial_screenshot':f'game-hud-initial-{width}.png'})
        page.close()
    browser.close()
print(json.dumps(results,ensure_ascii=False,indent=2))
(base/'BROWSER_RESULTS.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
