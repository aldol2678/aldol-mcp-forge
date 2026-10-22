"""Offline, network-free scanner tests. No arbitrary network calls in CI."""
import pathlib
import sys
import pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import site_policy as sp

@pytest.mark.parametrize("bad",[
    "http://public.example.com/","https://localhost/private",
    "https://127.0.0.1/private","https://[::1]/metadata",
    "https://user:pass@public.example.com/","https://public.example.com:8443/",
    "https://service.internal/policy","https://a.test/","https://public.example.com/path?secret=1",
    "https://169.254.169.254/latest/meta-data","https://public.example.com/\nHost:attacker"
])
def test_reject_private_or_ambiguous_urls(bad):
    with pytest.raises(ValueError):
        sp._clean_url(bad)

def test_public_url_accepts_only_normalized_https():
    host,path,url=sp._clean_url("https://Public.EXAMPLE.org/privacy#section")
    assert host=="public.example.org" and path=="/privacy"
    assert url=="https://public.example.org/privacy"

def test_disallow_mixed_private_dns_result(monkeypatch):
    fake=[
        (2,1,6,"",("8.8.8.8",443)),
        (2,1,6,"",("127.0.0.1",443)),
    ]
    monkeypatch.setattr(sp.socket,"getaddrinfo",lambda *args,**kwargs:fake)
    with pytest.raises(ValueError,match="공인 IP"):
        sp._resolved_global_ip("public.example.org")

def test_analyze_missing_is_not_automatic_legal_violation():
    r=sp.analyze("privacy","저희 서비스에 오신 것을 환영합니다.")
    assert r["legal_clearance"] is False
    assert r["total"]>=8
    assert all(x["status"]=="NOT_LOCATED" for x in r["checks"])
    assert r["review_status"]=="HUMAN_REVIEW_REQUIRED"

def test_templated_text_is_not_clearance():
    r=sp.analyze("terms","이용자 계정과 저작권을 다루며 서비스를 제공합니다. 책임 제한과 분쟁 처리 내용을 알립니다.")
    assert r["legal_clearance"] is False
    assert r["mentioned"]>0

def test_patch_plan_never_invents_facts_or_writes():
    r=sp.patch_plan("privacy","개인정보를 보호합니다.","{\"processors\":\"Supabase로 인증을 처리\",\"international\":\"싱가포르 데이터 리전 사용\"}")
    assert r["changes_applied"] is False
    assert r["legal_clearance"] is False
    by_field={a["section"]:a for a in r["suggested_changes"]}
    assert by_field["처리위탁"]["status"]=="READY_FOR_HUMAN_DRAFT"
    assert by_field["보유 및 이용 기간"]["status"]=="FACTS_REQUIRED"

def test_patch_plan_rejects_unverified_structure():
    for raw in ('{"admin":true}','[]','{"processors":123}','not_json'):
        with pytest.raises(ValueError):
            sp.patch_plan("privacy","sample",raw)

def test_compare_is_readonly_with_hashes_and_diff():
    a=sp.compare_versions("개인정보 항목: 이메일","개인정보 항목: 이메일\n보유기간은 별도 확인")
    assert a["changed"] and a["changes_applied"] is False and "+보유기간" in a["diff"]
    assert len(a["old_sha256"])==64

def test_scan_public_site_two_documents_no_external_links(monkeypatch):
    hit=[]
    docs={
       "https://public.example.org/":'''<html><body><a href="/privacy">개인정보처리방침</a><a href="/terms">이용약관</a><a href="https://evil.org/policy">privacy terms</a></body></html>''',
       "https://public.example.org/privacy":"<h1>개인정보처리방침</h1><p>처리 목적 및 개인정보의 보유기간 안내</p>",
       "https://public.example.org/terms":"<h1>이용약관</h1><p>서비스 범위 및 계정과 저작권</p>",
    }
    def fetch(url):
        hit.append(url)
        return url,docs[url]
    monkeypatch.setattr(sp,"_fetch_html",fetch)
    r=sp.scan_site("https://public.example.org/")
    assert set(r["found"])=={"privacy","terms"}
    assert r["legal_clearance"] is False
    assert len(hit)==3 and all("evil.org" not in x for x in hit)
    assert r["found"]["terms"]["audit"]["legal_clearance"] is False

def test_scan_does_not_execute_embedded_scripts(monkeypatch):
    html='''<script>alert("danger")</script><footer><a href="/terms">이용약관</a></footer>'''
    docs={"https://public.example.org/":html,
          "https://public.example.org/terms":"<h1>서비스 이용약관</h1><script>ignore me</script>"}
    monkeypatch.setattr(sp,"_fetch_html",lambda u:(u,docs[u]))
    r=sp.scan_site("https://public.example.org/")
    assert "danger" not in str(r) and "ignore me" not in str(r)
