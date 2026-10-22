"""No external network or repository changes: GitHub provider workflow contract tests."""
import asyncio
import base64
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import github_policy_pr as gh
from fastapi.testclient import TestClient
from main import app

OWNER="12345678-1234-4234-8234-123456789012"
SITE="https://studio.example.org"
REPO="example/policy-site"
PATH="docs/privacy.md"
OLD="개인정보처리방침\n기존 내용입니다."
NEW="개인정보처리방침\n개인정보 보유기간과 제3자 제공 사항을 검토하여 추가합니다."
GRANT={"rights_owner_id":OWNER,"site_url":SITE,"repository":REPO,
       "verified":True,"repository_id":754,"installation_id":891,
       "policy_paths":[PATH,"docs/terms.md"]}

def setup_env(monkeypatch):
    monkeypatch.setenv("RIGHTS_GITHUB_GRANTS_JSON",json.dumps([GRANT]))

class FakeGithub:
    def __init__(self,fail_at=None):
        self.calls=[]
        self.fail_at=fail_at
        self.branch_created=False
        self.pr_created=False
        self.last_put=None
        self.base_sha="a"*40
    async def request(self,method,path,payload=None,ok=(200,),params=None):
        self.calls.append((method,path,payload,params))
        if self.fail_at==(method,path):
            raise gh.GitHubGateError("GitHub API HTTP 503: transient")
        if method=="GET" and path=="/repos/"+REPO:
            return {"id":754,"full_name":REPO,"archived":False,"disabled":False,"default_branch":"main"}
        if method=="GET" and path=="/repos/"+REPO+"/contents/"+PATH:
            assert params=={"ref":"main"}
            return {"type":"file","size":len(OLD.encode()),"encoding":"base64",
                    "content":base64.b64encode(OLD.encode()).decode(),"sha":"b"*40}
        if method=="GET" and "/git/ref/heads/rights-policy/" in path:
            if self.branch_created:return {"ref":path}
            raise gh.GitHubGateError("GitHub API HTTP 404: branch missing")
        if method=="GET" and path=="/repos/"+REPO+"/git/ref/heads/main":
            return {"object":{"sha":self.base_sha}}
        if method=="POST" and path=="/repos/"+REPO+"/git/refs":
            assert payload["sha"]==self.base_sha
            self.branch_created=True
            return {"ref":payload["ref"]}
        if method=="PUT" and path=="/repos/"+REPO+"/contents/"+PATH:
            assert payload["sha"]=="b"*40
            assert base64.b64decode(payload["content"]).decode()==NEW
            self.last_put=payload
            return {"commit":{"sha":"c"*40}}
        if method=="POST" and path=="/repos/"+REPO+"/pulls":
            assert payload["draft"] is True
            assert payload["head"]==self.last_put["branch"]
            self.pr_created=True
            return {"number":48}
        if method=="GET" and path=="/repos/"+REPO+"/pulls/48":
            return {"number":48,"draft":True,"state":"open",
                    "head":{"ref":self.last_put["branch"]},"base":{"ref":"main"},
                    "html_url":"https://github.com/"+REPO+"/pull/48"}
        if method=="GET" and path=="/repos/"+REPO+"/pulls/48/files":
            return [{"filename":PATH}]
        raise AssertionError((method,path))

def test_no_scope_no_repo_change(monkeypatch):
    monkeypatch.delenv("RIGHTS_GITHUB_GRANTS_JSON",raising=False)
    with pytest.raises(gh.GitHubGateError):
        gh.get_grant(OWNER,SITE,REPO,PATH)

def test_owner_site_repo_path_match_required(monkeypatch):
    setup_env(monkeypatch)
    assert gh.get_grant(OWNER,SITE,REPO,PATH).repository_id==754
    for owner,site,repo,path in [
        (OWNER,SITE,"other/repo",PATH),(OWNER,"https://another.example.org",REPO,PATH),
        ("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",SITE,REPO,PATH),
        (OWNER,SITE,REPO,".github/workflows/ci.yml"),
        (OWNER,SITE,REPO,"../secrets.txt"),
        (OWNER,SITE,REPO,"docs/other.md")]:
        with pytest.raises(gh.GitHubGateError):
            gh.get_grant(owner,site,repo,path)

def test_unverified_site_denied(monkeypatch):
    g={**GRANT,"verified":False}
    monkeypatch.setenv("RIGHTS_GITHUB_GRANTS_JSON",json.dumps([g]))
    with pytest.raises(gh.GitHubGateError):gh.get_grant(OWNER,SITE,REPO,PATH)

def test_preview_readonly_and_full_digest(monkeypatch):
    setup_env(monkeypatch)
    api=FakeGithub()
    result=asyncio.run(gh.prepare(api,OWNER,SITE,REPO,PATH,NEW))
    assert result["status"]=="PREVIEW_ONLY"
    assert result["changes_applied"] is False
    assert result["approval_required"] is True
    assert "-기존 내용" in result["diff"]
    assert len(result["preview_digest"])==64
    assert all(method=="GET" for method,*_ in api.calls)

def test_wrong_digest_and_no_approval_never_write(monkeypatch):
    setup_env(monkeypatch)
    for digest,confirmed in [("0"*64,True),("1"*64,False),("",True)]:
        api=FakeGithub()
        with pytest.raises(gh.GitHubGateError):
            asyncio.run(gh.open_draft_pr(api,OWNER,SITE,REPO,PATH,NEW,digest,confirmed))
        assert not api.branch_created
        assert all(method=="GET" for method,*_ in api.calls)

def test_draft_pr_create_and_readback(monkeypatch):
    setup_env(monkeypatch)
    api=FakeGithub()
    p=asyncio.run(gh.prepare(api,OWNER,SITE,REPO,PATH,NEW))
    result=asyncio.run(gh.open_draft_pr(api,OWNER,SITE,REPO,PATH,NEW,p["preview_digest"],True))
    assert result["status"]=="DRAFT_PR_VERIFIED"
    assert result["number"]==48
    assert result["changed_files"]==[PATH]
    assert not result["merged"] and not result["deployed"]
    assert api.branch_created and api.pr_created

def test_repeated_branch_never_overwritten(monkeypatch):
    setup_env(monkeypatch)
    api=FakeGithub()
    p=asyncio.run(gh.prepare(api,OWNER,SITE,REPO,PATH,NEW))
    api.branch_created=True
    with pytest.raises(gh.GitHubGateError,match="브랜치"):
        asyncio.run(gh.open_draft_pr(api,OWNER,SITE,REPO,PATH,NEW,p["preview_digest"],True))
    assert not api.pr_created

def test_ambiguous_post_write_error_stops_retry(monkeypatch):
    setup_env(monkeypatch)
    api=FakeGithub(fail_at=("POST","/repos/"+REPO+"/pulls"))
    p=asyncio.run(gh.prepare(api,OWNER,SITE,REPO,PATH,NEW))
    with pytest.raises(gh.GitHubPartialWrite) as ex:
        asyncio.run(gh.open_draft_pr(api,OWNER,SITE,REPO,PATH,NEW,p["preview_digest"],True))
    assert api.branch_created and api.last_put
    assert ex.value.branch.startswith("rights-policy/")

def test_pr_api_requires_authenticated_session():
    c=TestClient(app)
    payload={"site_url":SITE,"repository":REPO,"document_path":PATH,"proposed_text":NEW}
    assert c.post("/api/site-policy/github/prepare",json=payload,headers={"x-rights-client":"web"}).status_code==401
    assert c.post("/api/site-policy/github/submit",json={
        **payload,"expected_preview_digest":"0"*64,"confirmed":True},
        headers={"x-rights-client":"web"}).status_code==401
