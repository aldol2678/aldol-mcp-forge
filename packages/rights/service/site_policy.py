"""External-site policy reconnaissance. Public HTTPS only, minimal bounded reads, no site writes.

Every downloaded byte is untrusted. Network fetches pin a DNS-validated global IP
and validate the original hostname's TLS certificate to avoid DNS rebinding/SSRF.
No JavaScript, cookies, auth, redirects to new hosts, or remote commands.
"""
from __future__ import annotations
from difflib import unified_diff
from html.parser import HTMLParser
from hashlib import sha256
import http.client
import ipaddress
import json
import re
import socket
import ssl
from urllib.parse import urljoin, urlsplit, urlunsplit

MAX_HTML = 160_000
MAX_TEXT = 30_000
MAX_HOST = 253
MAX_PATH = 700

CLAUSES = {
    "privacy": {
        "purpose": ("처리 목적", ("처리 목적", "수집 목적", "purpose of processing", "use of information")),
        "items": ("처리하는 개인정보 항목", ("개인정보 항목", "수집하는 항목", "수집 항목", "personal information we collect")),
        "retention": ("보유 및 이용 기간", ("보유 기간", "보유기간", "retention period", "how long we keep")),
        "deletion": ("파기 절차 및 방법", ("파기 절차", "파기방법", "삭제 방법", "deletion of personal")),
        "third_parties": ("제3자 제공", ("제3자 제공", "third-party sharing", "share your information")),
        "processors": ("처리위탁", ("처리위탁", "업무 위탁", "service providers", "processors")),
        "international": ("국외이전", ("국외 이전", "국외이전", "international transfer", "outside your country")),
        "rights": ("정보주체 권리", ("정보주체", "권리 행사", "열람·정정", "your privacy rights")),
        "contact": ("개인정보 담당자 연락처", ("개인정보 보호책임자", "개인정보 보호 담당", "privacy officer", "contact us")),
        "cookies": ("자동수집 장치", ("쿠키", "cookie", "tracking technologies")),
    },
    "terms": {
        "service": ("서비스 범위", ("서비스의 제공", "서비스 내용", "서비스 목적", "description of services")),
        "accounts": ("계정 및 회원", ("회원가입", "계정", "회원", "user account")),
        "rights": ("이용자 저작물·권리", ("저작권", "이용자 콘텐츠", "콘텐츠의 권리", "intellectual property")),
        "fees": ("결제·취소 조건 (해당 시)", ("결제", "취소", "환불", "payment", "refund")),
        "changes": ("약관의 변경", ("약관 변경", "약관의 개정", "terms changes", "modify these terms")),
        "termination": ("탈퇴·서비스 종료", ("탈퇴", "해지", "계약 종료", "termination")),
        "liability": ("책임 제한", ("책임", "손해배상", "면책", "liability")),
        "disputes": ("분쟁 처리", ("분쟁", "관할법원", "준거법", "dispute")),
        "contact": ("사업자 정보·연락처", ("연락처", "사업자", "문의", "contact")),
    },
}

def _clean_url(url: str) -> tuple[str, str, str]:
    if not isinstance(url, str) or len(url) > 1600 or any(ord(c) < 32 for c in url):
        raise ValueError("HTTPS URL 길이 또는 제어문자를 확인하세요.")
    p = urlsplit(url.strip())
    if p.scheme.lower() != "https" or p.username or p.password or p.query:
        raise ValueError("인증정보·쿼리 없이 공개 HTTPS URL만 사용하세요.")
    try: port = p.port
    except ValueError: raise ValueError("잘못된 포트입니다.")
    if port not in (None, 443):
        raise ValueError("표준 HTTPS(443) 포트만 허용합니다.")
    host = (p.hostname or "").rstrip(".").lower()
    if not host or len(host) > MAX_HOST or any(ord(c) > 127 for c in host) or not re.fullmatch(r"[a-z0-9.-]+", host):
        raise ValueError("유효한 공개 도메인만 허용합니다.")
    if (host in ("localhost",) or host.endswith((".local", ".internal", ".localhost", ".test", ".invalid", ".example", ".onion")) or
        "." not in host or any(not label or len(label)>63 or label.startswith("-") or label.endswith("-") for label in host.split("."))):
        raise ValueError("내부/테스트 도메인 또는 잘못된 도메인은 검사할 수 없습니다.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP 주소 입력은 허용하지 않습니다.")
    path = p.path or "/"
    if len(path) > MAX_PATH:
        raise ValueError("URL 경로가 너무 깁니다.")
    return host, path, urlunsplit(("https", host, path, "", ""))

def _resolved_global_ip(host: str) -> str:
    addrs = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
    ips = [ipaddress.ip_address(a[4][0]) for a in addrs]
    if not ips or any(not ip.is_global for ip in ips):
        raise ValueError("공인 IP가 아닌 주소로 연결이 확인되어 요청을 차단했습니다.")
    return str(ips[0])

class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname: str, ip: str):
        super().__init__(hostname, port=443, timeout=5, context=ssl.create_default_context())
        self._ip=ip
    def connect(self):
        sock=socket.create_connection((self._ip,443),timeout=5)
        self.sock=self._context.wrap_socket(sock,server_hostname=self.host)

def _fetch_html(url: str) -> tuple[str, str]:
    host,path,safe_url=_clean_url(url)
    ip=_resolved_global_ip(host)
    conn=_PinnedHTTPS(host,ip)
    try:
        conn.request("GET",path,headers={"Host":host, "Accept":"text/html", "User-Agent":"ALDOL-RIGHTS-PolicyAudit/0.4 (public document check; no JS)", "Connection":"close"})
        resp=conn.getresponse()
        if resp.status in (301,302,303,307,308):
            # No redirects to avoid cross-origin and SSRF gadgets.
            raise ValueError("사이트가 다른 주소로 이동시켰습니다. 최종 공개 HTTPS 주소를 직접 제공하세요.")
        if resp.status != 200:
            raise ValueError(f"공개 페이지를 가져올 수 없습니다 (HTTP {resp.status}).")
        if resp.getheader("Content-Encoding", "identity").lower() not in ("", "identity"):
            raise ValueError("압축 응답은 이 최소 스캐너에서 지원하지 않습니다.")
        content_type=resp.getheader("Content-Type","").lower()
        if "text/html" not in content_type:
            raise ValueError("HTML 공개 페이지만 지원합니다.")
        raw=resp.read(MAX_HTML+1)
        if len(raw)>MAX_HTML:
            raise ValueError("페이지 크기 제한(160KB)을 초과했습니다.")
        # UTF-8 preferred for Korean/English; invalid sequences are replaced, never executed.
        enc_match=re.search(r"charset=([a-z0-9_-]+)",content_type)
        enc=enc_match.group(1) if enc_match else "utf-8"
        if enc not in ("utf-8","euc-kr","cp949","iso-8859-1"):
            enc="utf-8"
        return safe_url,raw.decode(enc,errors="replace")
    finally:
        conn.close()

class _Extract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip=0; self.links=[]; self.text=[]; self.active_link=None
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style","noscript","svg","iframe"): self.skip+=1
        if tag=="a":
            a=dict(attrs)
            href=a.get("href","")
            if href:
                self.links.append([href,""])
                self.active_link=len(self.links)-1
        if tag in ("p","h1","h2","h3","li","section","br"):self.text.append("\n")
    def handle_endtag(self,tag):
        if tag in ("script","style","noscript","svg","iframe") and self.skip:self.skip-=1
        if tag=="a":self.active_link=None
    def handle_data(self,data):
        if not self.skip:
            value=data.strip()
            if value:self.text.append(value+" ")
            if self.active_link is not None and value:
                i=self.active_link
                self.links[i][1]=(self.links[i][1]+" "+value).strip()[:130]
    def result(self):
        return re.sub(r"[ \t]+"," ","".join(self.text)).strip()[:MAX_TEXT]

def _classify_label(label: str, url: str) -> str | None:
    value=(label+" "+url).casefold()
    if any(x in value for x in ("개인정보", "privacy", "개인 정보 처리")):return "privacy"
    if any(x in value for x in ("이용약관","서비스 약관","terms","user-agreement","user_agreement")):return "terms"
    return None

def analyze(kind: str, text: str, jurisdiction: str="KR") -> dict:
    if kind not in CLAUSES or not isinstance(text,str) or len(text)>MAX_TEXT:
        raise ValueError("문서 종류(privacy/terms) 또는 3만 자 이내 본문을 확인하세요.")
    if jurisdiction not in ("KR","GENERAL"):
        raise ValueError("현재 KR/GENERAL만 지원합니다.")
    t=re.sub(r"\s+"," ",text).casefold()
    findings=[]
    for key,(label,phrases) in CLAUSES[kind].items():
        matched=next((v for v in phrases if v.casefold() in t),None)
        findings.append({"field":key,"label":label,"status":"MENTIONED" if matched else "NOT_LOCATED",
                         "note":"관련 단어의 존재만 확인됨, 법령 충족 증거가 아님" if matched else "본문에서 문구를 찾지 못함. 다른 표현/별도 페이지일 수 있음",
                         "needs_human_review":True})
    return {"kind":kind,"jurisdiction":jurisdiction,"checks":findings,
            "mentioned":sum(f["status"]=="MENTIONED" for f in findings),"total":len(findings),
            "document_sha256":sha256(text.encode()).hexdigest(),
            "legal_clearance":False,"review_status":"HUMAN_REVIEW_REQUIRED",
            "warning":"표면적 키워드 조사만 수행합니다. 실제 개인정보 흐름·법적 근거·계약 내용·동의·접근 권한을 자동 확인할 수 없습니다."}

def scan_site(url: str) -> dict:
    home,html=_fetch_html(url)
    parsed=_Extract();parsed.feed(html)
    host,_,_=_clean_url(home)
    candidates={}
    initial=_classify_label("",home)
    if initial:candidates[initial]=home
    for href,label in parsed.links[:160]:
        kind=_classify_label(label,href)
        if not kind or kind in candidates:continue
        try:
            candidate=urljoin(home,href)
            h,_,safe=_clean_url(candidate)
            if h==host:candidates[kind]=safe
        except (ValueError,TypeError):continue
    found={}
    for kind,link in list(candidates.items())[:2]:
        try:
            u,body=_fetch_html(link) if link!=home else (home,html)
            parser=_Extract();parser.feed(body);text=parser.result()
            found[kind]={"url":u,"length":len(text),"excerpt":text[:450],
                         "audit":analyze(kind,text)}
        except (ValueError,OSError,ssl.SSLError) as e:
            found[kind]={"url":link,"status":"UNAVAILABLE","reason":str(e)[:180]}
    return {"site":home,"found":found,"discovered_links":candidates,
            "missing":[k for k in ("privacy","terms") if k not in found],
            "pages_requested":1+sum(u!=home for u in candidates.values()),
            "warning":"공개 정적 HTML만 조사합니다. JavaScript 생성 페이지, 숨겨진 처리, 실제 수집정보와 법적 준수 여부는 검증되지 않습니다.",
            "untrusted_data":True,"legal_clearance":False}

FACTS={
    "privacy":{"purpose":"실제 처리 목적","items":"실제 수집/처리 항목","retention":"정확한 보유기간","deletion":"파기 절차와 백업",
               "third_parties":"제3자 제공","processors":"처리위탁/하위처리자","international":"국외이전 근거·수령자","rights":"정보주체 권리 행사","contact":"책임자 및 연락처","cookies":"쿠키/추적기"},
    "terms":{"service":"제공 서비스","accounts":"회원 및 계정 규칙","rights":"콘텐츠 권리 귀속","fees":"유료 서비스 조건",
             "changes":"약관 변경 절차","termination":"해지·종료","liability":"책임과 면책","disputes":"분쟁 처리","contact":"운영자 정보"}
}
def patch_plan(kind: str, text: str, verified_facts_json: str="{}") -> dict:
    if len(verified_facts_json)>10000:raise ValueError("운영정보가 너무 깁니다.")
    try: facts=json.loads(verified_facts_json)
    except json.JSONDecodeError:raise ValueError("운영정보는 JSON 객체여야 합니다.")
    if not isinstance(facts,dict) or any(k not in FACTS.get(kind,{}) or not isinstance(v,str) or len(v)>1500 for k,v in facts.items()):
        raise ValueError("허용된 항목에 해당하는 문자열 운영정보만 전달하세요.")
    audit=analyze(kind,text)
    changes=[]
    for f in audit["checks"]:
        key=f["field"]
        if key=="fees" and kind=="terms" and key not in facts:continue
        if f["status"]=="NOT_LOCATED" or key in facts:
            proven=key in facts and bool(facts[key].strip())
            changes.append({"section":f["label"],"action":"REVIEW_EXISTING_OR_ADD","verified_fact":facts[key] if proven else None,
                            "draft_note":("운영자가 확인한 사실을 바탕으로 조문을 작성하고 법적 검토를 받으세요." if proven
                                          else "서비스 운영 정보를 확인한 후에만 구체적인 조항을 작성하세요."),
                            "status":"READY_FOR_HUMAN_DRAFT" if proven else "FACTS_REQUIRED"})
    return {"kind":kind,"source_sha256":audit["document_sha256"],"suggested_changes":changes,
            "requires_authorized_site_owner":True,"changes_applied":False,"legal_clearance":False,
            "warning":"본 도구는 사이트에 게시하지 않고 확인된 운영정보로 개정 계획만 제시합니다. 원문 복제/단정적 준법 표현을 피하세요."}

def compare_versions(old: str, new: str) -> dict:
    if len(old)>MAX_TEXT or len(new)>MAX_TEXT:raise ValueError("각 버전은 3만 자 이하여야 합니다.")
    lines=list(unified_diff(old.splitlines(),new.splitlines(),fromfile="before",tofile="proposed",lineterm="",n=2))
    return {"changed":old!=new, "old_sha256":sha256(old.encode()).hexdigest(),
            "new_sha256":sha256(new.encode()).hexdigest(),"diff":"\n".join(lines)[:18000],
            "diff_truncated":len("\n".join(lines))>18000,
            "review_status":"HUMAN_REVIEW_REQUIRED","changes_applied":False}
