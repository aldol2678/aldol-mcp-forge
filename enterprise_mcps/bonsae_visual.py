"""Bounded BONSAE render/pixel adapter. Never fetches caller-supplied URLs.

Only operator-installed Playwright Chromium is used. Rendering runs in a fresh
process with scripting disabled, no persistent profile and all network denied.
Geometric/pixel measurements are evidence, not a claim of semantic visual QA.
"""
from __future__ import annotations
import base64
import hashlib
import io
import json
import os
import signal
import subprocess
import sys
import threading

MAX_HTML = 131072
MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 8_000_000
_RENDER_LOCK = threading.BoundedSemaphore(1)


def image_measurements(raw: bytes) -> dict:
    """Decode real supplied/rendered bytes; bounded format/size/dimensions."""
    from PIL import Image, ImageStat
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("image exceeds 2 MiB")
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    with Image.open(io.BytesIO(raw)) as image:
        if image.format not in ("PNG", "JPEG", "WEBP"):
            raise ValueError("Only PNG/JPEG/WEBP pixels supported")
        if image.width * image.height > MAX_PIXELS:
            raise ValueError("image exceeds 8 million pixels")
        image.load()
        rgb = image.convert("RGB")
        sample = rgb.copy()
        sample.thumbnail((256, 256))
        stat = ImageStat.Stat(sample)
        extrema = sample.getextrema()
        # Image dynamic range is deliberately not labelled text contrast.
        return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                "format": image.format, "width": image.width, "height": image.height,
                "sample_mean_rgb": [round(x, 2) for x in stat.mean],
                "sample_channel_extrema": [list(x) for x in extrema],
                "uniform_sample": all(a == b for a, b in extrema),
                "pixel_decode_performed": True,
                "not_measured": ["semantic layout", "typographic meaning", "brand fit",
                                 "text/background contrast without element masks"]}


def inspect_image(encoded: str) -> dict:
    if not isinstance(encoded, str) or len(encoded) > (MAX_IMAGE_BYTES * 4 // 3 + 8):
        raise ValueError("image_base64 must be bounded base64 text")
    if encoded.startswith("data:"):
        raise ValueError("Provide raw base64, not a URL or data URI")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("image_base64 is invalid") from exc
    return image_measurements(raw)


def render_html(html: str, css: str, viewports: list[int], intent_tokens: dict | None = None) -> dict:
    if not isinstance(html, str) or not html.strip() or len(html) > MAX_HTML:
        raise ValueError("html must contain 1..131072 characters")
    if not isinstance(css, str) or len(css) > MAX_HTML:
        raise ValueError("css must contain at most 131072 characters")
    if (not isinstance(viewports, list) or not 1 <= len(viewports) <= 3
            or any(type(x) is not int or x not in (390, 820, 1280) for x in viewports)
            or len(set(viewports)) != len(viewports)):
        raise ValueError("viewports must be a subset of [390,820,1280]")
    intent_tokens = intent_tokens or {}
    if (not isinstance(intent_tokens, dict) or len(intent_tokens) > 30
            or any(not isinstance(k, str) or not k.startswith("--") or len(k) > 80
                   or not isinstance(v, str) or len(v) > 120 for k, v in intent_tokens.items())):
        raise ValueError("intent_tokens must be a bounded CSS custom-property map")
    if not _RENDER_LOCK.acquire(blocking=False):
        return {"rendered": False, "reason": "RENDER_BUSY", "retryable": True}
    try:
        proc = subprocess.Popen([sys.executable, "-m", "enterprise_mcps.bonsae_visual"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True)
        try:
            stdout, _ = proc.communicate(json.dumps({"html": html, "css": css,
                "viewports": viewports, "intent_tokens": intent_tokens}, ensure_ascii=False), timeout=45)
        except subprocess.TimeoutExpired:
            # Kill the entire dedicated process group, including browser descendants.
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            return {"rendered": False, "reason": "RENDER_TIMEOUT"}
        if proc.returncode != 0:
            # Avoid returning stderr which may contain environment/browser paths.
            return {"rendered": False, "reason": "BROWSER_UNAVAILABLE_OR_RENDER_FAILED"}
        return json.loads(stdout)
    except (subprocess.TimeoutExpired, ValueError):
        return {"rendered": False, "reason": "RENDER_TIMEOUT_OR_INVALID_RESULT"}
    finally:
        _RENDER_LOCK.release()


_MEASURE = r"""({tokens}) => {
 const visible = e => {const r=e.getBoundingClientRect(), s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
 const loc = e => e.id ? '#'+e.id : e.tagName.toLowerCase()+(e.classList.length?'.'+[...e.classList].slice(0,2).join('.'):'');
 const all=[...document.body.querySelectorAll('*')].filter(visible).slice(0,2000);
 const clipped=all.filter(e=>{const r=e.getBoundingClientRect();return r.left< -1||r.right>innerWidth+1}).slice(0,30).map(e=>({selector:loc(e),rect:e.getBoundingClientRect().toJSON()}));
 const targets=all.filter(e=>e.matches('button,a,input:not([type=hidden]),select,textarea,[role=button]'));
 const small=targets.filter(e=>{const r=e.getBoundingClientRect();return r.width<44||r.height<44}).slice(0,30).map(e=>({selector:loc(e),width:Math.round(e.getBoundingClientRect().width),height:Math.round(e.getBoundingClientRect().height)}));
 const textClips=all.filter(e=>{const s=getComputedStyle(e);return (['hidden','clip'].includes(s.overflowX)&&e.scrollWidth>e.clientWidth+1)||(['hidden','clip'].includes(s.overflowY)&&e.scrollHeight>e.clientHeight+1)}).slice(0,30).map(e=>({selector:loc(e),scrollWidth:e.scrollWidth,clientWidth:e.clientWidth,scrollHeight:e.scrollHeight,clientHeight:e.clientHeight}));
 const parse=c=>{const m=c.match(/^rgba?\(([\d.]+)[, ]+([\d.]+)[, ]+([\d.]+)(?:[, /]+([\d.]+))?\)$/);return m?m.slice(1).map(Number):null};
 const lum=v=>{let a=v.slice(0,3).map(x=>{x/=255;return x<=.04045?x/12.92:Math.pow((x+.055)/1.055,2.4)});return .2126*a[0]+.7152*a[1]+.0722*a[2]};
 const contrast=[];let unknownContrast=0;
 for(const e of all.filter(e=>[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())).slice(0,300)){
   const s=getComputedStyle(e),fg=parse(s.color);let p=e,bg=null,ambiguous=false;
   while(p){const ps=getComputedStyle(p);if(ps.backgroundImage!=='none'||Number(ps.opacity)<1||ps.filter!=='none'||ps.mixBlendMode!=='normal')ambiguous=true;
    const c=parse(ps.backgroundColor);if(c&&c.length===4&&c[3]>0&&c[3]<1){ambiguous=true;break}if(c&&(c.length<4||c[3]===1)){bg=c;break}p=p.parentElement;}
   if(!fg||!bg||ambiguous||(fg.length===4&&fg[3]!==1)){unknownContrast++;continue}
   const ratio=(Math.max(lum(fg),lum(bg))+.05)/(Math.min(lum(fg),lum(bg))+.05),fs=parseFloat(s.fontSize),large=fs>=24||(fs>=18.66&&Number(s.fontWeight)>=700),minimum=large?3:4.5;
   contrast.push({selector:loc(e),ratio:Math.round(ratio*100)/100,minimum,passes:ratio>=minimum});
 }
 const observedTokens=Object.fromEntries(Object.keys(tokens).map(k=>[k,getComputedStyle(document.documentElement).getPropertyValue(k).trim()]));
 return {viewport:innerWidth,height:innerHeight,documentWidth:document.documentElement.scrollWidth,documentHeight:document.documentElement.scrollHeight,visibleElements:all.length,domTruncated:document.body.querySelectorAll('*').length>2000,overflow:document.documentElement.scrollWidth>innerWidth+1,clippedElements:clipped,smallTouchTargets:small,clippedContainers:textClips,contrast,unknownContrastCount:unknownContrast,observedTokens,tokenDrift:Object.keys(tokens).filter(k=>observedTokens[k]!==tokens[k]).map(k=>({token:k,expected:tokens[k],observed:observedTokens[k]})),fontFamilies:[...new Set(all.slice(0,300).map(e=>getComputedStyle(e).fontFamily))]};
}"""


def _worker(data: dict) -> dict:
    from playwright.sync_api import sync_playwright
    blocked = []
    results = []
    with sync_playwright() as p:
        options = {"headless": True, "args": ["--disable-dev-shm-usage", "--disable-gpu", "--no-zygote"]}
        executable = os.environ.get("BONSAE_BROWSER_EXECUTABLE")
        if executable:
            options["executable_path"] = executable
        browser = p.chromium.launch(**options)
        try:
            for width in data["viewports"]:
                context = browser.new_context(viewport={"width": width, "height": 820},
                    java_script_enabled=False, service_workers="block", accept_downloads=False,
                    reduced_motion="reduce")
                def deny(route):
                    blocked.append(route.request.resource_type)
                    route.abort()
                context.route("**/*", deny)
                page = context.new_page()
                page.set_default_timeout(5000)
                # CSP is first and cannot be weakened by later document policies.
                policy = "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src 'none'; script-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'\">"
                page.set_content(policy + data["html"], wait_until="domcontentloaded", timeout=5000)
                if data["css"]:
                    page.add_style_tag(content=data["css"])
                # Page evaluate is trusted inspector code; document scripts stay disabled.
                measurements = page.evaluate(_MEASURE, {"tokens": data["intent_tokens"]})
                raw = page.screenshot(type="png", full_page=False, timeout=5000,
                                      animations="disabled")
                measurements["screenshot"] = image_measurements(raw)
                measurements["screenshot"]["coverage"] = "viewport only; below-fold content not visually inspected"
                results.append(measurements)
                context.close()
        finally:
            browser.close()
    return {"rendered": True, "engine": "Playwright Chromium", "javascript_enabled": False,
            "network_policy": "deny all external/file requests; CSP restricts passive resources",
            "blocked_request_count": len(blocked), "viewports": results,
            "limits": ["geometry and pixel measurements only", "no semantic aesthetic judgment",
                       "focus/state transitions not exercised", "CJK glyph availability not independently certified",
                       "overlap detection is limited to viewport/container clipping; intentional stacking not judged"]}


if __name__ == "__main__":
    try:
        print(json.dumps(_worker(json.loads(sys.stdin.read(300000))), ensure_ascii=False))
    except Exception:
        sys.exit(1)
