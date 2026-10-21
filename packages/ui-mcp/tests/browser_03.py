"""Browser E2E: mobile/desktop layout, hit targets, toggles, host binding updates.

No remote requests. Open self-contained HTML with page.set_content.
"""
from pathlib import Path
import json
import shutil
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parents[1]
chromium=shutil.which('chromium') or shutil.which('google-chrome')
if not chromium: raise SystemExit('Chrome/Chromium required')
results=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=chromium,headless=True,args=['--no-sandbox'])
    for doc,width,height in [('web-dashboard',360,780),('web-dashboard',390,844),('web-dashboard',768,1024),('web-dashboard',1280,800),('expedition-hud-v03',360,740),('expedition-hud-v03',390,844),('expedition-hud-v03',768,1024),('expedition-hud-v03',1280,800)]:
        page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
        errs=[];page.on('pageerror',lambda err: errs.append(str(err)))
        page.set_default_timeout(4500)
        page.set_content((root/'examples'/f'{doc}.html').read_text(encoding='utf-8'),wait_until='load')
        page.wait_for_timeout(100)
        report=page.evaluate('''() => ({docWidth:document.documentElement.scrollWidth, vw:innerWidth, vh:innerHeight,
            buttons:[...document.querySelectorAll('button')].filter(x=>x.getClientRects().length>0).map(x=>({txt:x.textContent.trim(),w:x.getBoundingClientRect().width,h:x.getBoundingClientRect().height})),
            panels:[...document.querySelectorAll('.alui-hud-overlay>.alui-stack>.alui-panel')].map(x=>x.getBoundingClientRect().toJSON())})''')
        assert report['docWidth'] <= report['vw'] + 1,(doc,width,'overflow',report)
        assert all(b['w']>=44 and b['h']>=44 for b in report['buttons']),(doc,width,'hit targets',report['buttons'])
        page.screenshot(path=str(root/'examples'/f'{doc}-initial-{width}.png'),full_page=True)
        if doc=='expedition-hud-v03':
            top,bottom=report['panels'][0],report['panels'][-1]
            assert bottom['top']-top['bottom'] >= 18, (doc,width,'battle area hidden',top,bottom)
            assert bottom['bottom']<=height+1,(doc,width,'bottom panel clipped',bottom)
            page.get_by_role('button',name='전술').click()
            assert page.locator('[data-alui-id="tactics"]').is_visible()
            page.get_by_role('button',name='반격 요청').click()
            assert 'battle:counter' in page.locator('.alui-demo-toast').inner_text()
            page.get_by_role('button',name='상태이상').click()
            assert page.locator('[data-alui-id="conditions"]').is_visible()
            assert not page.locator('[data-alui-id="tactics"]').is_visible()
            page.keyboard.press('Escape')
            assert not page.locator('[data-alui-id="conditions"]').is_visible()
            num=page.evaluate('''() => window.ALDOLUI.setState(document.querySelector('.alui-hud-overlay'),
               {'health':48, 'health-title':'군단 체력 48 / 100', 'foe-count':'1', 'battle-status':'회복 중'})''')
            assert num==4,(doc,width,'bindings',num)
            assert page.get_by_role('progressbar').get_attribute('aria-valuenow')=='48'
            assert page.get_by_text('군단 체력 48 / 100').is_visible()
        else:
            page.get_by_role('button',name='가이드 펼치기').click()
            assert page.locator('[data-alui-id="guide"]').is_visible()
            page.keyboard.press('Escape')
            assert not page.locator('[data-alui-id="guide"]').is_visible()
            num=page.evaluate('''() => window.ALDOLUI.setState(document.querySelector('.alui-app'),
                   {'project-count':21,'qa-status':'READY','work-progress':87})''')
            assert num==3, (doc,width,'bindings',num)
            assert page.get_by_text('READY',exact=True).is_visible()
            assert page.get_by_role('progressbar').get_attribute('aria-valuenow')=='87'
            page.get_by_role('button',name='검증 이벤트 보내기').click()
            assert 'studio:review' in page.locator('.alui-demo-toast').inner_text()
        assert not errs,(doc,width,'errors',errs)
        page.screenshot(path=str(root/'examples'/f'{doc}-{width}.png'),full_page=True)
        results.append({'document':doc,'viewport':width,'horizontal_overflow':False,'hit_targets_ok':True,
                        'interaction':'PASS','binding':'PASS','page_errors':0,'status':'PASS'})
        print(doc,width,'PASS',flush=True)
        page.close()
    browser.close()
(root/'BROWSER_RESULTS_03.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
