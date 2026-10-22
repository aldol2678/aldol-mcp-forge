"""GitHub App delegated draft-PR workflow for authorized RIGHTS site operators.

Rights read-only MCP keys NEVER grant GitHub write. No automatic merge, deploy, tag,
branch overwrite or edits to arbitrary paths. GitHub installation access tokens
are minted on demand for exactly one preapproved repository.
"""
from __future__ import annotations
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import unified_diff
import hashlib
import json
import os
import re
from urllib.parse import quote, urlsplit
from uuid import UUID
import httpx

MAX_DOCUMENT=30000
MAX_GITHUB_BYTES=80000
API="https://api.github.com"
PATH_RE=re.compile(r"^[A-Za-z0-9_./-]{3,220}$")
REPO_RE=re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

class GitHubGateError(ValueError): pass
class GitHubPartialWrite(RuntimeError):
    def __init__(self,branch:str,reason:str):
        self.branch=branch
        super().__init__(reason)

@dataclass(frozen=True)
class Grant:
    rights_owner_id:str
    repository:str
    repository_id:int
    installation_id:int
    site_url:str
    policy_paths:tuple[str,...]

def normalize_site_url(site_url:str)->str:
    p=urlsplit(site_url)
    if (p.scheme!="https" or not p.hostname or p.username or p.password or p.query or p.fragment
        or p.path not in ("","/") or p.port not in (None,443)):
        raise GitHubGateError("검증된 HTTPS 사이트 루트만 허용합니다.")
    host=p.hostname.lower().rstrip(".")
    if not re.fullmatch(r"[a-z0-9.-]{4,253}",host) or host in ("localhost",) or host.endswith((".local",".internal",".localhost")):
        raise GitHubGateError("잘못된 사이트 도메인입니다.")
    return "https://"+host

def allowed_path(path:str)->str:
    if (not isinstance(path,str) or not PATH_RE.fullmatch(path) or path.startswith(("/","."))
        or "//" in path or any(p in ("",".","..") for p in path.split("/"))
        or not path.endswith((".md",".mdx",".txt",".html",".htm"))):
        raise GitHubGateError("정책 문서 경로만 허용합니다. 위험한 경로가 감지됐습니다.")
    if path.startswith((".github/","node_modules/")):
        raise GitHubGateError("설정·실행 경로는 정책 파일로 취급할 수 없습니다.")
    return path

def get_grant(owner_id:str,site_url:str,repository:str,path:str)->Grant:
    """Only server-operator configured mapping may authorize a site-to-repo write."""
    try:
        owner_id=str(UUID(owner_id))
        site_url=normalize_site_url(site_url)
        path=allowed_path(path)
        if not REPO_RE.fullmatch(repository):raise GitHubGateError("잘못된 저장소 식별자입니다.")
    except (TypeError,ValueError) as e:
        raise GitHubGateError("권한 검사 입력을 확인하세요.") from e
    try:raw=json.loads(os.environ.get("RIGHTS_GITHUB_GRANTS_JSON","[]"))
    except (ValueError,TypeError):raise GitHubGateError("관리자 권한 설정이 유효하지 않습니다.")
    if not isinstance(raw,list):raise GitHubGateError("관리자 권한 설정이 유효하지 않습니다.")
    matches=[]
    for item in raw:
        if not isinstance(item,dict):continue
        if (item.get("rights_owner_id")==owner_id
            and item.get("site_url")==site_url
            and item.get("repository")==repository
            and item.get("verified") is True
            and path in item.get("policy_paths",[])
            and isinstance(item.get("repository_id"),int) and item["repository_id"]>0
            and isinstance(item.get("installation_id"),int) and item["installation_id"]>0):
            matches.append(item)
    if len(matches)!=1:
        raise GitHubGateError("해당 계정과 사이트·저장소·정책 파일의 승인된 매핑이 없습니다.")
    m=matches[0]
    return Grant(owner_id,repository,m["repository_id"],m["installation_id"],site_url,
                 tuple(m["policy_paths"]))

def validate_proposal(text:str)->str:
    if not isinstance(text,str) or not 20<=len(text)<=MAX_DOCUMENT:
        raise GitHubGateError("수정본은 20자 이상, 30,000자 이하여야 합니다.")
    if "\x00" in text or any(0<=ord(ch)<9 for ch in text):
        raise GitHubGateError("바이너리/제어 문자가 포함됐습니다.")
    return text

def _github_headers(token:str)->dict:
    return {"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
            "X-GitHub-Api-Version":"2022-11-28","User-Agent":"ALDOL-RIGHTS-PolicyPR/0.5"}

class GitHubAppAPI:
    def __init__(self,grant:Grant):self.grant=grant;self.client=None;self.token=None
    async def __aenter__(self):
        try:
            import jwt
            app_id=int(os.environ["RIGHTS_GITHUB_APP_ID"])
            pem=os.environ["RIGHTS_GITHUB_APP_PRIVATE_KEY"].replace("\\n","\n")
            if not pem.startswith("-----BEGIN"):raise ValueError()
        except (KeyError,ValueError,ImportError):
            raise GitHubGateError("GitHub App의 안전한 서버 비밀키 구성이 완료되지 않았습니다.")
        now=int(datetime.now(timezone.utc).timestamp())
        assertion=jwt.encode({"iat":now-60,"exp":now+540,"iss":app_id},pem,algorithm="RS256")
        self.client=httpx.AsyncClient(base_url=API,timeout=12,follow_redirects=False)
        try:
            r=await self.client.post(
                "/app/installations/"+str(self.grant.installation_id)+"/access_tokens",
                headers=_github_headers(assertion),
                json={"repository_ids":[self.grant.repository_id],
                      "permissions":{"contents":"write","pull_requests":"write","metadata":"read"}})
            r.raise_for_status()
            self.token=r.json()["token"]
        except (httpx.HTTPError,KeyError,ValueError):
            await self.client.aclose()
            raise GitHubGateError("GitHub App 설치 권한을 확인할 수 없습니다.")
        return self
    async def __aexit__(self,*args):
        if self.client:await self.client.aclose()
        self.token=None
    async def request(self,method:str,path:str,payload:dict|None=None,ok=(200,),params:dict|None=None):
        # No arbitrary URL accepted; paths always assembled from validated repo/path.
        if not path.startswith("/") or "://" in path or "?" in path or "//" in path:
            raise GitHubGateError("허용되지 않은 GitHub API 경로입니다.")
        try:
            r=await self.client.request(method,path,headers=_github_headers(self.token),json=payload,params=params)
        except httpx.HTTPError as e:
            raise GitHubGateError("GitHub API 네트워크 연결에 실패했습니다.") from e
        if r.status_code not in ok:
            raise GitHubGateError(f"GitHub API HTTP {r.status_code}: 저장소 권한·충돌·사용량을 확인하세요.")
        return r.json()

async def repo_context(api,grant:Grant)->dict:
    r=await api.request("GET","/repos/"+grant.repository)
    if (r.get("id")!=grant.repository_id or r.get("full_name","").casefold()!=grant.repository.casefold()
        or r.get("archived") or r.get("disabled") or not isinstance(r.get("default_branch"),str)):
        raise GitHubGateError("저장소 ID/권한/운영 상태가 미확인입니다.")
    return r

async def read_doc(api,grant:Grant,path:str,base:str)->dict:
    doc=await api.request("GET","/repos/"+grant.repository+"/contents/"+quote(path,safe="/"),params={"ref":base})
    if doc.get("type")!="file" or doc.get("size",MAX_GITHUB_BYTES+1)>MAX_GITHUB_BYTES or doc.get("encoding")!="base64":
        raise GitHubGateError("파일 유형/크기를 검사할 수 없습니다.")
    raw=base64.b64decode(doc.get("content","").replace("\n",""),validate=True)
    if len(raw)>MAX_GITHUB_BYTES:raise GitHubGateError("원본 파일이 너무 큽니다.")
    try:orig=raw.decode("utf-8")
    except UnicodeDecodeError:raise GitHubGateError("UTF-8 정책 파일만 지원합니다.")
    return {"content":orig,"sha":doc["sha"]}

def digest(grant:Grant,path:str,old_sha:str,text:str,base:str)->str:
    data=json.dumps([grant.rights_owner_id,grant.repository_id,grant.site_url,path,base,old_sha,text],ensure_ascii=False,separators=(",",":"))
    return hashlib.sha256(data.encode()).hexdigest()

async def prepare(api,owner_id:str,site_url:str,repository:str,path:str,proposed_text:str)->dict:
    grant=get_grant(owner_id,site_url,repository,path)
    text=validate_proposal(proposed_text)
    info=await repo_context(api,grant)
    base=info["default_branch"]
    original=await read_doc(api,grant,path,base)
    if text==original["content"]:raise GitHubGateError("변경 사항이 없습니다.")
    preview=digest(grant,path,original["sha"],text,base)
    diff="\n".join(unified_diff(original["content"].splitlines(),text.splitlines(),
                                 fromfile="current:"+path,tofile="proposed:"+path,lineterm="",n=3))
    if len(diff)>16000:
        raise GitHubGateError("변경 비교가 너무 큽니다. 문서 변경 범위를 줄여주세요.")
    return {"status":"PREVIEW_ONLY","repository":grant.repository,"repository_id":grant.repository_id,
            "site_url":grant.site_url,"document_path":path,"base_branch":base,"current_sha":original["sha"],
            "preview_digest":preview,"diff":diff,"changes_applied":False,"approval_required":True,
            "legal_clearance":False,
            "warning":"실제 운영사실을 확인하고 사이트 운영자가 검토해야 합니다. PR 작성 시 GitHub 알림/CI가 실행될 수 있습니다."}

async def open_draft_pr(api,owner_id:str,site_url:str,repository:str,path:str,proposed_text:str,
                        expected_preview_digest:str,confirmed:bool)->dict:
    if not confirmed or not re.fullmatch(r"[a-f0-9]{64}",expected_preview_digest or ""):
        raise GitHubGateError("승인된 미리보기 해시 및 명시적인 Draft PR 생성 확인이 필요합니다.")
    plan=await prepare(api,owner_id,site_url,repository,path,proposed_text)
    if plan["preview_digest"]!=expected_preview_digest:
        raise GitHubGateError("원본이 바뀌었거나 수정본이 달라졌습니다. 미리보기를 다시 확인하세요.")
    grant=get_grant(owner_id,site_url,repository,path)
    base=plan["base_branch"]
    short=expected_preview_digest[:14]
    branch="rights-policy/"+short
    refs="/repos/"+repository+"/git/refs"
    # Before external writes, ensure generated branch is not already claimed.
    try:
        await api.request("GET","/repos/"+repository+"/git/ref/heads/"+branch)
    except GitHubGateError as e:
        if "HTTP 404" not in str(e):raise
    else:raise GitHubGateError("동일 변경 브랜치가 존재합니다. 해당 PR/브랜치를 확인하세요.")
    base_ref=await api.request("GET","/repos/"+repository+"/git/ref/heads/"+quote(base,safe=""))
    base_sha=base_ref.get("object",{}).get("sha")
    if not isinstance(base_sha,str) or not re.fullmatch("[a-f0-9]{40}",base_sha):
        raise GitHubGateError("기준 브랜치 커밋 확인 실패")
    await api.request("POST",refs,{"ref":"refs/heads/"+branch,"sha":base_sha},ok=(201,))
    # From here an ambiguous error must not trigger automatic retry.
    partial=True
    try:
        file_api="/repos/"+repository+"/contents/"+quote(path,safe="/")
        data=await api.request("PUT",file_api,{
            "message":"docs(rights): propose reviewed "+path+" update",
            "content":base64.b64encode(proposed_text.encode()).decode(),
            "sha":plan["current_sha"],"branch":branch},ok=(200,))
        if not data.get("commit",{}).get("sha"):
            raise GitHubGateError("커밋 결과를 확인하지 못했습니다.")
        pr=await api.request("POST","/repos/"+repository+"/pulls",{
            "title":"docs(rights): review "+path+" policy revision",
            "head":branch,"base":base,"draft":True,
            "body":"ALDOL RIGHTS policy proposal for "+site_url+
                   "\n\nThis PR is an **unapproved legal document draft**. Verify operational facts, privacy law, consents, subprocessors and retention before merge. No legal clearance is claimed. Source preview SHA256: `"+expected_preview_digest+"`."},
            ok=(201,))
        number=pr.get("number")
        if not isinstance(number,int):raise GitHubGateError("PR 번호를 확인하지 못했습니다.")
        readback=await api.request("GET","/repos/"+repository+"/pulls/"+str(number))
        if (not readback.get("draft") or readback.get("head",{}).get("ref")!=branch
            or readback.get("base",{}).get("ref")!=base or readback.get("state")!="open"):
            raise GitHubGateError("PR readback 검증에 실패했습니다.")
        changed=await api.request("GET","/repos/"+repository+"/pulls/"+str(number)+"/files")
        if len(changed)!=1 or changed[0].get("filename")!=path:
            raise GitHubGateError("PR이 허용된 정책 파일 하나만 변경하는지 확인하지 못했습니다.")
        return {"status":"DRAFT_PR_VERIFIED","repository":repository,"branch":branch,
                "number":number,"url":readback.get("html_url",""),
                "changed_files":[path],"merged":False,"deployed":False,
                "legal_clearance":False,"verification":"draft/open/branch/base/one file readback PASS"}
    except Exception as e:
        raise GitHubPartialWrite(branch,"Draft PR 생성 또는 검증이 불완전합니다. 같은 요청을 자동 재시도하지 말고 브랜치와 PR 상태를 먼저 확인하세요.") from e
