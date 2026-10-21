"""Generate, bundle and exercise a real React consumer; npm ci --prefix tests/react-runtime first."""
import json, os, subprocess, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from ui_core import core
runtime=ROOT/'tests/react-runtime'
output=core.render((ROOT/'examples/web-dashboard.json').read_text(),'react-tsx',quality_mode='enforce')
(runtime/'Generated.tsx').write_text(output['component_tsx'])
(runtime/'style.css').write_text(output['css'])
subprocess.run([str(runtime/'node_modules/.bin/esbuild'),str(runtime/'main.tsx'),'--bundle','--format=iife','--outfile='+str(runtime/'bundle.js')],check=True)
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_EXECUTABLE',p.chromium.executable_path),args=['--no-sandbox'],headless=True)
 page=b.new_page(viewport={'width':390,'height':844});page.set_default_timeout(5000)
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.set_content('<style>'+output['css']+'</style><div id="root"></div>')
 page.add_script_tag(content=(runtime/'bundle.js').read_text())
 page.get_by_role('button',name='가이드 펼치기').click()
 assert page.locator('[data-alui-id="guide"]').is_visible()
 page.keyboard.press('Escape')
 assert not page.locator('[data-alui-id="guide"]').is_visible()
 assert page.get_by_text('READY',exact=True).is_visible()
 assert page.get_by_role('progressbar').get_attribute('aria-valuenow')=='87'
 page.get_by_role('button',name='검증 이벤트 보내기').click()
 assert page.locator('body').get_attribute('data-action')=='studio:review'
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 assert not errors,errors
 print(json.dumps({'status':'PASS','viewport':390,'checks':['bundle','mount','toggle','escape','host_values','host_action','no_overflow','no_page_errors']}))
 b.close()
