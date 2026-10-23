"""Browser evidence from repository examples; optional actual Jamo files.

Only this test harness executes trusted project fixtures. Analysis tools never do.
Network is blocked; browser profiles/storage are ephemeral. Android is not tested.
"""
import argparse
import base64
import hashlib
import json
import os
import re
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ui_core import core, reference, visual


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--jamo-current'); ap.add_argument('--jamo-previous')
    ap.add_argument('--output',default=str(ROOT/'evidence/v04/browser'))
    args=ap.parse_args(); out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    font_css=''
    font_package=os.getenv('UI_QA_FONT_PACKAGE')
    if font_package:
        base=Path(font_package)
        # Optional known local font fixture; no fetch in browser or analysis tools.
        font_css=(base/'400.css').read_text()
        font_css=re.sub(r'url\(\./([^)]*)\)',lambda m:'url(data:font/woff2;base64,'+base64.b64encode((base/m[1]).read_bytes()).decode()+')',font_css)
        font_css+='body,button,input,select{font-family:"Noto Sans KR",sans-serif!important}'
    def settle(page):
        if font_css: page.add_style_tag(content=font_css)
        page.evaluate('document.fonts.ready')
        page.wait_for_timeout(350)
    reports=[]
    def save_compare(name,a,b,mode,width,same_state=True):
        r=visual.compare(base64.b64encode(a).decode(),base64.b64encode(b).decode(),mode,
                         'mobile' if width<600 else 'tablet' if width<1000 else 'desktop',same_state=same_state)
        artifact=r['diff_artifact']
        if artifact:
            path=name+'-diff.png'; (out/path).write_bytes(base64.b64decode(artifact.pop('data')))
            artifact['test_artifact_path']=path
        (out/(name+'.json')).write_text(json.dumps(r,indent=2))
        return r
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.getenv('CHROMIUM_EXECUTABLE',p.chromium.executable_path),
                                  headless=True,args=['--no-sandbox'])
        for name,target in [('web-dashboard','web-html'),('expedition-hud-v03','game-hud-html')]:
            html=core.render((ROOT/'examples'/f'{name}.json').read_text(),target,quality_mode='enforce')['preview_html']
            analysis=reference.analyze(html)
            assert analysis['components'] and analysis['interaction_candidates']
            (out/(name+'-reference.json')).write_text(json.dumps(analysis,indent=2))
            for width,height in ((360,780),(390,844),(768,1024),(1280,800)):
                page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
                page.route('**/*',lambda route:route.abort())
                errors=[]; page.on('pageerror',lambda err:errors.append(str(err)))
                page.set_content(html); page.add_style_tag(content='*,*::before,*::after{animation:none!important;transition:none!important}')
                settle(page)
                a=page.screenshot(type='jpeg',quality=75); (out/f'{name}-{width}-before.jpg').write_bytes(a)
                same=save_compare(f'{name}-{width}-identical',a,a,'pixel',width)
                assert same['pixel_difference']['ratio']==0 and not same['changed_regions']
                selector='.alui-panel' if target=='game-hud-html' else '.alui-card'
                node=page.locator(selector).first
                assert node.count()
                box=node.bounding_box(); assert box
                node.evaluate('(e)=>e.style.transform="translateY(48px)"')
                b=page.screenshot(type='jpeg',quality=75); (out/f'{name}-{width}-shift.jpg').write_bytes(b)
                diff=save_compare(f'{name}-{width}-shift',a,b,'layout',width)
                assert diff['changed_regions'] and diff['layout_similarity']<1
                assert any(r['x']<box['x']+box['width'] and r['x']+r['width']>box['x'] and r['y']<box['y']+box['height']+48 and r['y']+r['height']>box['y'] for r in diff['changed_regions'])
                node.evaluate('(e)=>{e.style.transform="";e.style.visibility="hidden"}')
                c=page.screenshot(type='jpeg',quality=75)
                missing=save_compare(f'{name}-{width}-missing',a,c,'region',width)
                assert missing['changed_regions'] and missing['pixel_difference']['ratio']>0
                assert not errors,errors
                reports.append({'project':name,'viewport':[width,height],'comparison_checks':3,
                                'intentional_mutation':'48px panel/card translation and hidden panel/card',
                                'status':'PASS','page_errors':len(errors)})
                page.close()
        if args.jamo_current:
            current=Path(args.jamo_current).resolve()
            analysis=reference.analyze(current.read_text())
            (out/'jamo-reference.json').write_text(json.dumps(analysis,indent=2))
            assert any(c['role']=='panel' for c in analysis['components'])
            sources=[('current',current)]
            if args.jamo_previous: sources.insert(0,('previous',Path(args.jamo_previous).resolve()))
            for width,height in ((360,780),(390,844),(768,1024),(1280,800)):
                shots={}
                for version,path in sources:
                    page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
                    page.route('http://**/*',lambda route:route.abort()); page.route('https://**/*',lambda route:route.abort())
                    errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
                    page.goto(path.as_uri()+'#stage-1');page.wait_for_timeout(150)
                    page.add_style_tag(content='*,*::before,*::after{animation:none!important;transition:none!important}')
                    settle(page)
                    before=page.screenshot(type='jpeg',quality=75); shots[version]=before
                    (out/f'jamo-{version}-{width}.jpg').write_bytes(before)
                    result={'project':'jamo','version':version,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                            'viewport':[width,height], 'horizontal_overflow':page.evaluate('document.documentElement.scrollWidth>innerWidth+1'),
                            'page_errors':len(errors),'scope':'initial classic stage; no gameplay acceptance'}
                    if version=='current' and width<800:
                        page.locator('#classicSheetToggle').click()
                        page.wait_for_timeout(350)
                        panel=page.locator('#classicSheetPanel'); box=panel.bounding_box()
                        result['editor_panel_box']=box
                        result['editor_panel_within_viewport']=bool(box and box['x']>=-1 and box['y']>=-1 and box['x']+box['width']<=width+1 and box['y']+box['height']<=height+1)
                        result['editor_scroll']=panel.locator('.sheet-scroll').evaluate('(e)=>({height:e.clientHeight,scrollHeight:e.scrollHeight})')
                        after=page.screenshot(type='jpeg',quality=75);(out/f'jamo-open-{width}.jpg').write_bytes(after)
                        diff=save_compare(f'jamo-popup-{width}',before,after,'region',width,False)
                        assert diff['changed_regions']
                        result['popup_change_detected']=True
                    result['status']='OBSERVED'  # tested state is evidence, never automatic UI approval
                    reports.append(result);page.close()
                if len(shots)==2:
                    diff=save_compare(f'jamo-version-change-{width}',shots['previous'],shots['current'],'region',width,False)
                    assert diff['changed_regions']
        else:
            reports.append({'project':'jamo','status':'NOT_RUN','reason':'optional private local file not supplied'})
        browser.close()
    summary={'browser':'Chromium','android_device_test':'NOT_RUN','capture':'JPEG quality 75, DPR 1, viewport only; no resizing',
             'font_fixture':'Noto Sans KR 5.3.1, normalized QA font' if font_css else 'environment fonts; typography not certified',
             'reports':reports,'status':'PASS'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
