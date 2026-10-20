#!/usr/bin/env python3
"""ALDOL Game Ops v0.3: offline static HTML/ZIP QA and optional browser scenario QA.
Dependencies: Python 3.10+, node (for JS syntax), playwright + Chromium for browser checks.
Not a security boundary: run only in an OS-isolated sandbox with no secrets and no network.
"""
from __future__ import annotations
import argparse
import base64
import datetime
import hashlib
from html.parser import HTMLParser
import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import zipfile
from urllib.parse import urlparse, unquote

MAX_SINGLE=12*1024*1024
MAX_ARCHIVE=40*1024*1024
MAX_ENTRIES=700
VIEWPORTS={"mobile320": (320,568),"mobile360":(360,640),"mobile390":(390,844),"desktop":(1365,850)}


def digest(data):return hashlib.sha256(data).hexdigest()
def record(checks,key,status,detail,**kw):
    checks.append({"id":key,"status":status,"detail":str(detail)[:750],**kw})
def file_safe(name):
    p=PurePosixPath(name)
    return bool(name and not name.startswith('/') and '\\' not in name and not any(x in ('.','..') for x in p.parts))

class Structure(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title=False;self.heading=False;self.viewport=False;self.script_sources=[];self.stylesheets=[];self.images=[];self.inline_js=[];self.inline_css=[];self.current=None;self.parts=[];self.heading_count=0
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=='title':self.title=True
        if tag=='h1':self.heading_count+=1
        if tag=='meta' and d.get('name','').lower()=='viewport':self.viewport=True
        if tag=='script':
            if d.get('src'):self.script_sources.append(d['src'])
            elif not d.get('type') or d.get('type','').lower() in ('text/javascript','application/javascript','module'):self.current='js';self.parts=[]
        if tag=='style':self.current='css';self.parts=[]
        if tag=='link' and d.get('rel','').lower()=='stylesheet' and d.get('href'):self.stylesheets.append(d['href'])
        if tag=='img' and d.get('src'):self.images.append(d['src'])
    def handle_data(self,data):
        if self.current:self.parts.append(data)
    def handle_endtag(self,tag):
        if (tag=='script' and self.current=='js') or (tag=='style' and self.current=='css'):
            s=''.join(self.parts)
            (self.inline_js if self.current=='js' else self.inline_css).append(s)
            self.current=None;self.parts=[]

def read_artifact(path):
    path=Path(path).resolve(); b=path.read_bytes()
    if len(b)>MAX_ARCHIVE:raise ValueError('MAX_ARCHIVE exceeded')
    if path.suffix.lower() in ('.html','.htm'):
        if len(b)>MAX_SINGLE:raise ValueError('MAX_SINGLE exceeded')
        return {path.name:b},path.name,digest(b)
    if path.suffix.lower()!='.zip':raise ValueError('only .html, .htm or .zip is supported')
    files={};total=0
    with zipfile.ZipFile(path) as z:
        infos=z.infolist()
        if len(infos)>MAX_ENTRIES:raise ValueError('MAX_ENTRIES exceeded')
        for info in infos:
            if info.is_dir():continue
            if not file_safe(info.filename):raise ValueError('unsafe archive path: '+info.filename)
            if ((info.external_attr >> 16) & 0o170000) == 0o120000:raise ValueError('symbolic links prohibited')
            total+=info.file_size
            if info.file_size>MAX_SINGLE or total>MAX_ARCHIVE:raise ValueError('archive decompressed size limit exceeded')
            files[info.filename]=z.read(info)
    candidates=sorted((x for x in files if x.lower().endswith(('.html','.htm'))),key=lambda x:(PurePosixPath(x).name.lower() not in ('index.html','index.htm'),x.count('/'),x))
    if not candidates:raise ValueError('ZIP has no HTML entry point')
    return files,candidates[0],digest(b)

def resolve_resource(src, entry, files):
    if src.startswith(('data:','#','blob:')):return 'embedded',None
    parsed=urlparse(src)
    if parsed.scheme or src.startswith('//'):return 'remote',None
    # paths restricted to archive relative; absolute-path references are not locally resolved
    if src.startswith('/'):return 'missing',None
    raw=unquote(parsed.path)
    parts=list(PurePosixPath(entry).parent.parts) if PurePosixPath(entry).parent!=PurePosixPath('.') else []
    for part in raw.split('/'):
        if part in ('','.'):continue
        if part=='..':
            if not parts:return 'missing',None
            parts.pop()
        else:parts.append(part)
    target='/'.join(parts)
    return ('local',target) if target in files else ('missing',target)

def data_uri(src,entry,files):
    kind,target=resolve_resource(src,entry,files)
    if kind=='local':
        mime=mimetypes.guess_type(target)[0] or 'application/octet-stream'
        return 'data:'+mime+';base64,'+base64.b64encode(files[target]).decode()
    return src

def embed_for_browser(html, entry, files):
    """Rewrites only direct static references. Dynamic imports/fetch remain unavailable."""
    from html import escape
    # inline script links; project-relative JS included in configured archive
    # robust replacement with actual match
    def repl_link_script(m):
        tag=m.group(0); mm=re.search(r'\bsrc\s*=\s*["\']([^"\']+)["\']',tag,re.I)
        if not mm:return tag
        kind,target=resolve_resource(mm.group(1),entry,files)
        if kind!='local':return tag
        js=files[target].decode('utf-8','replace').replace('</script','<\\/script')
        return '<script>'+js+'</script>'
    html=re.sub(r'<script\b[^>]*\bsrc=["\'][^"\']+["\'][^>]*>\s*</script\s*>',repl_link_script,html,flags=re.I|re.S)
    def repl_link(m):
        tag=m.group(0)
        if not re.search(r'\brel=["\']stylesheet["\']',tag,re.I):return tag
        mm=re.search(r'\bhref=["\']([^"\']+)["\']',tag,re.I)
        if not mm:return tag
        kind,target=resolve_resource(mm.group(1),entry,files)
        if kind!='local':return tag
        css=files[target].decode('utf-8','replace').replace('</style','<\\/style')
        return '<style>'+css+'</style>'
    html=re.sub(r'<link\b[^>]*>',repl_link,html,flags=re.I)
    def repl_img(m):
        tag=m.group(0);mm=re.search(r'\bsrc=["\']([^"\']+)["\']',tag,re.I)
        if not mm:return tag
        return tag.replace(mm.group(1),data_uri(mm.group(1),entry,files))
    html=re.sub(r'<img\b[^>]*>',repl_img,html,flags=re.I)
    # CSS url for local resources, including embedded <style>; external URLs remain blocked
    def css_url(m):
        url=m.group(2)
        if url.startswith(('data:','#')):return m.group(0)
        new=data_uri(url,entry,files)
        return 'url("'+new+'")'
    html=re.sub(r'url\(\s*(["\']?)([^)"\']+)\1\s*\)',css_url,html,flags=re.I)
    # sandboxed about:blank origin does not reliably expose localStorage; provide explicit simulated storage.
    stub='''<script>
window.__ALDOL_STORAGE__=window.__ALDOL_STORAGE__||{};
Object.defineProperty(window,'localStorage',{configurable:true,value:{
 getItem:k=>Object.prototype.hasOwnProperty.call(window.__ALDOL_STORAGE__,k)?window.__ALDOL_STORAGE__[k]:null,
 setItem:(k,v)=>{window.__ALDOL_STORAGE__[k]=String(v)},removeItem:k=>delete window.__ALDOL_STORAGE__[k],
 clear:()=>{window.__ALDOL_STORAGE__={}}, key:i=>Object.keys(window.__ALDOL_STORAGE__)[i]||null,
 get length(){return Object.keys(window.__ALDOL_STORAGE__).length}
}});
</script>'''
    if re.search(r'<head\b[^>]*>',html,re.I):html=re.sub(r'(<head\b[^>]*>)',lambda m:m.group(1)+stub,html,count=1,flags=re.I)
    else:html=stub+html
    return html

def syntax_check(code,checks,name):
    with tempfile.NamedTemporaryFile(mode='w',suffix='.js',encoding='utf-8',delete=False) as f:
        f.write(code);tmp=f.name
    try:
        proc=subprocess.run(['node','--check',tmp],timeout=8,capture_output=True,text=True)
        record(checks,name,'PASS' if proc.returncode==0 else 'FAIL',proc.stderr.strip()[:300] if proc.returncode else 'JS syntax valid')
    except FileNotFoundError:record(checks,name,'UNKNOWN','Node.js unavailable')
    except subprocess.TimeoutExpired:record(checks,name,'UNKNOWN','Node.js syntax check timeout')
    finally:Path(tmp).unlink(missing_ok=True)

def static_checks(files,entry,checks):
    html=files[entry].decode('utf-8','replace');p=Structure();p.feed(html)
    record(checks,'static.doctype','PASS' if re.search(r'<!doctype\s+html',html,re.I) else 'FAIL','HTML doctype')
    record(checks,'static.title','PASS' if p.title else 'FAIL','Title element')
    record(checks,'static.viewport','PASS' if p.viewport else 'FAIL','Viewport meta element')
    for i,js in enumerate(p.inline_js):
        if js.strip():syntax_check(js,checks,'static.js.inline.'+str(i+1))
    resources=p.script_sources+p.stylesheets+p.images
    for src in sorted(set(resources)):
        kind,target=resolve_resource(src,entry,files)
        stat='PASS' if kind in ('local','embedded') else 'UNKNOWN' if kind=='remote' else 'FAIL'
        record(checks,'static.resource.'+src[:80],stat,'resource '+kind+': '+(target or src))
        if kind=='local' and target.endswith(('.js','.mjs')):syntax_check(files[target].decode('utf-8','replace'),checks,'static.js.asset.'+target)
    return html

def browser_checks(html,profile,checks,output):
    try:from playwright.sync_api import sync_playwright,TimeoutError as PTimeout
    except ImportError:
        record(checks,'browser.available','UNKNOWN','playwright is not installed');return
    chromium=os.environ.get('ALDOL_CHROMIUM','/usr/bin/chromium')
    if not Path(chromium).exists():
        record(checks,'browser.available','UNKNOWN','Chromium executable not found: '+chromium);return
    def load(page):page.set_content(html,wait_until='load',timeout=11000)
    with sync_playwright() as pw:
        try:browser=pw.chromium.launch(executable_path=chromium,headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--disable-gpu'])
        except Exception as e:record(checks,'browser.available','UNKNOWN',str(e)[:300]);return
        try:
            for vp in profile.get('viewports',['mobile320','mobile360','mobile390','desktop']):
                if vp not in VIEWPORTS:record(checks,'responsive.'+str(vp),'UNKNOWN','Unknown viewport');continue
                w,h=VIEWPORTS[vp];ctx=browser.new_context(viewport={'width':w,'height':h},has_touch=vp.startswith('mobile'),is_mobile=vp.startswith('mobile'),accept_downloads=False)
                ctx.route('**/*',lambda route:route.abort()) # prevent external network access
                page=ctx.new_page();page.set_default_timeout(2500)
                errors=[];blocked=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('requestfailed',lambda req:blocked.append(req.url[:120]))
                page.on('popup',lambda pp:pp.close())
                try:
                    load(page)
                    for tab in profile.get('responsive_tabs',[]):
                        try:
                            selector=tab.get('selector');page.locator(selector).first.click(timeout=2500)
                        except Exception as e:record(checks,f'responsive.{vp}.tab.{tab.get("id","?")}','FAIL',str(e)[:170]);continue
                        key=f'responsive.{vp}.{tab.get("id","tab")}'
                        state=page.evaluate('''() => ({scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,bodyWidth:document.body.scrollWidth,innerWidth:window.innerWidth})''')
                        ok=max(state['scrollWidth'],state['bodyWidth'])<=state['clientWidth']+1
                        record(checks,key+'.overflow','PASS' if ok else 'FAIL',state,viewport=vp)
                    if not profile.get('responsive_tabs'):
                        state=page.evaluate('''() => ({scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,bodyWidth:document.body.scrollWidth})''')
                        record(checks,f'responsive.{vp}.overflow','PASS' if max(state['scrollWidth'],state['bodyWidth'])<=state['clientWidth']+1 else 'FAIL',state,viewport=vp)
                    for target in (profile.get('touch_targets',[]) if vp.startswith('mobile') else []):
                        try:
                            loc=page.locator(target['selector']).first
                            box=loc.bounding_box(timeout=2000)
                            if not box:record(checks,f'responsive.{vp}.target.{target["id"]}','UNKNOWN','not rendered',viewport=vp);continue
                            minimum=int(target.get('min_px',44));value=min(box['width'],box['height']);status='PASS' if value>=minimum else 'FAIL'
                            record(checks,f'responsive.{vp}.target.{target["id"]}',status,f'{box["width"]:.0f}x{box["height"]:.0f}px, minimum {minimum}px',viewport=vp)
                        except Exception as e:record(checks,f'responsive.{vp}.target.{target["id"]}','UNKNOWN',str(e)[:150],viewport=vp)
                    if profile.get('screenshots',True):
                        target=output/(f'{vp}.png');page.screenshot(path=str(target),full_page=True,animations='disabled',timeout=7000)
                    record(checks,f'responsive.{vp}.errors','PASS' if not errors else 'FAIL','; '.join(errors[:3]) if errors else 'no uncaught JavaScript errors',viewport=vp)
                    if blocked:record(checks,f'responsive.{vp}.remote','UNKNOWN','External or unresolved requests blocked: '+', '.join(blocked[:5]),viewport=vp)
                except Exception as e:record(checks,f'responsive.{vp}.load','UNKNOWN',str(e)[:250],viewport=vp)
                finally:ctx.close()
            # Game-specific scenarios, each isolated from each other
            for scenario in profile.get('scenarios',[]):
                sid=scenario['id'];ctx=browser.new_context(viewport={'width':1365,'height':850},accept_downloads=False)
                ctx.route('**/*',lambda route:route.abort())
                page=ctx.new_page();page.set_default_timeout(3000)
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('popup',lambda pp:pp.close())
                try:
                    load(page)
                    for k,step in enumerate(scenario['steps'],1):
                        kind=step['action'];selector=step.get('selector');locator=page.locator(selector).first if selector else None
                        if kind=='click':locator.click()
                        elif kind=='tap':locator.tap()
                        elif kind=='fill':locator.fill(step['value'])
                        elif kind=='select':locator.select_option(step['value'])
                        elif kind=='wait':page.wait_for_timeout(min(int(step.get('ms',100)),2000))
                        elif kind=='assert_count':
                            count=page.locator(selector).count()
                            if count!=step['equals']:raise AssertionError(f'count={count}, expected={step["equals"]}')
                        elif kind=='assert_text':
                            actual=locator.inner_text()
                            if step['contains'] not in actual:raise AssertionError(f'expected text {step["contains"]!r}, observed {actual[:120]!r}')
                        elif kind=='assert_visible':
                            if not locator.is_visible():raise AssertionError('not visible: '+selector)
                        elif kind=='assert_state':
                            root=step.get('root','__JELLY_LAB_DEBUG__');method=step.get('method','snapshot')
                            # only simple identifiers; no user-supplied evaluated code
                            if not re.fullmatch(r'[a-zA-Z_$][\w$]*',root) or not re.fullmatch(r'[a-zA-Z_$][\w$]*',method):raise ValueError('Invalid debug interface identifier')
                            actual=page.evaluate('''arg=>{let obj=window[arg.root];if(!obj||typeof obj[arg.method]!=='function')throw new Error('debug hook missing');let data=obj[arg.method]();for(let key of arg.path.split('.')){data=data?.[key]};return data}''',{'root':root,'method':method,'path':step['path']})
                            if actual!=step['equals']:raise AssertionError(f'{step["path"]}: got {actual!r}, expected {step["equals"]!r}')
                        elif kind=='assert_storage_key':
                            value=page.evaluate('key=>localStorage.getItem(key)',step['key'])
                            if bool(value)!=bool(step.get('present',True)):raise AssertionError('storage state mismatch')
                        elif kind=='reload_simulated':
                            # emulate reload, preserving stub storage explicitly; not a real browser reload
                            st=page.evaluate('window.__ALDOL_STORAGE__||{}');page.evaluate('st=>{window.__ALDOL_STORAGE__=st}',st)
                            load(page)
                        else:raise ValueError('Unsupported action: '+kind)
                        record(checks,f'scenario.{sid}.{k}','PASS',kind+' '+(selector or step.get('path','')))
                    if errors:record(checks,f'scenario.{sid}.errors','FAIL','; '.join(errors[:3]))
                except Exception as e:
                    record(checks,f'scenario.{sid}.{k}','FAIL',str(e)[:350]);
                    try:page.screenshot(path=str(output/f'scenario_{sid}_FAIL.png'),full_page=True,timeout=5000)
                    except Exception:pass
                finally:ctx.close()
        finally:browser.close()

def run(path,profile,out):
    checks=[];out.mkdir(parents=True,exist_ok=True)
    try:
        files,entry,sha=read_artifact(path)
        h=static_checks(files,entry,checks)
        testhtml=embed_for_browser(h,entry,files)
        browser_checks(testhtml,profile,checks,out)
        artifact={"source":str(Path(path).resolve()),"sha256":sha,"entry":entry,"files_count":len(files)}
    except Exception as e:
        record(checks,'artifact.open','FAIL',str(e));artifact={"source":str(path),"sha256":None,"entry":None}
    summary={x:sum(1 for c in checks if c['status']==x) for x in ('PASS','FAIL','UNKNOWN')}
    report={"engine":"ALDOL Game Ops HTML QA v0.3.0","created_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"artifact":artifact,"environment":{"browser":"Chromium via Playwright if installed","method":"set_content about:blank + emulated localStorage","network":"abort all external browser requests","real_device":False,"file_protocol_verified":False},"checks":checks,"summary":summary}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

def compare(base,candidate,out):
    b={c['id']:c for c in base['checks']};c={x['id']:x for x in candidate['checks']}
    regressed=[{"id":key,"before":b[key]['status'],"after":c[key]['status']} for key in b.keys()&c.keys() if b[key]['status']=='PASS' and c[key]['status']=='FAIL']
    resolved=[{"id":key,"before":b[key]['status'],"after":c[key]['status']} for key in b.keys()&c.keys() if b[key]['status']=='FAIL' and c[key]['status']=='PASS']
    missing=sorted(b.keys()-c.keys());added=sorted(c.keys()-b.keys())
    result={"engine":"ALDOL Game Ops regression v0.3.0","baseline_sha256":base['artifact']['sha256'],"candidate_sha256":candidate['artifact']['sha256'],"identical_input":base['artifact']['sha256']==candidate['artifact']['sha256'],"new_regressions":regressed,"resolved":resolved,"missing_checks":missing,"added_checks":added,"verdict":"BLOCKED" if regressed else "UNKNOWN" if missing else "NO_REGRESSION_DETECTED","scope":"compare only matching test IDs; untested behavior is UNKNOWN"}
    (out/'regression.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

def main():
    a=argparse.ArgumentParser(description='Offline HTML/ZIP static, browser and regression QA')
    a.add_argument('target',type=Path);a.add_argument('--profile',type=Path,required=False);a.add_argument('--output',type=Path,required=True);a.add_argument('--baseline',type=Path)
    args=a.parse_args();profile=json.loads(args.profile.read_text(encoding='utf-8')) if args.profile else {}
    args.output.mkdir(parents=True,exist_ok=True)
    report=run(args.target,profile,args.output/'candidate')
    result={'candidate':report['summary'],'candidate_sha256':report['artifact']['sha256']}
    if args.baseline:
        baseline=run(args.baseline,profile,args.output/'baseline')
        result['baseline']=baseline['summary']
        result['regression']=compare(baseline,report,args.output)
    else:result['regression']={'verdict':'UNKNOWN','reason':'No baseline artifact provided'}
    (args.output/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result.get('regression',{}).get('verdict')=='BLOCKED':return 2
    return 0 if report['summary']['FAIL']==0 else 1

if __name__=='__main__':sys.exit(main())
