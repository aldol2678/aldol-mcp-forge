"""ALDOL RIGHTS policy lifecycle and privacy-rights routes, scoped to RIGHTS only."""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
import store

router = APIRouter(prefix="/api/legal", tags=["legal"])

class SignupAgreement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    terms_id: UUID
    terms_accepted: bool

class DocumentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["privacy", "terms"]
    content: str = Field(min_length=400, max_length=30000)
    effective_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

class DraftEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=400, max_length=30000)
    effective_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    revision: int = Field(ge=1)

class PublishApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    verified_operator_contact: bool
    verified_retention_disposal: bool
    verified_vendors_transfers: bool
    reviewed_by_human: bool

class Acceptance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    terms_id: UUID
    accepted: bool

class PrivacyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_type: Literal["access","rectification","erasure","restriction"]

async def user_identity(request: Request):
    token = request.cookies.get("rights_access", "")
    if not token:
        raise HTTPException(401, "로그인이 필요합니다.")
    result = await store.call("GET","/auth/v1/user",token)
    if not result.get("id") or result.get("is_anonymous"):
        raise HTTPException(401, "정식 계정 로그인이 필요합니다.")
    return {"id":result["id"], "email":result.get("email",""), "token":token}

async def admin_identity(user=Depends(user_identity)):
    rows = await store.rows("rights_policy_admins", user["token"], "select=owner_id&owner_id=eq."+user["id"])
    if not rows:
        raise HTTPException(403, "RIGHTS 정책 관리자 권한이 필요합니다.")
    return user

async def published(kind: str):
    if kind not in ("privacy","terms"):
        raise HTTPException(404, "지원하지 않는 문서입니다.")
    docs = await store.rows("rights_legal_documents", None, "select=doc_id,kind,version,content,effective_on,published_at&kind=eq."+kind+"&status=eq.published&order=version.desc&limit=1")
    return docs[0] if docs else None

async def require_terms(user=Depends(user_identity)):
    terms = await published("terms")
    if not terms:
        raise HTTPException(503, "이용약관이 아직 게시되지 않았습니다. 운영자에게 문의하세요.")
    q = "select=doc_id&doc_id=eq."+terms["doc_id"]+"&limit=1"
    accepted = await store.rows("rights_policy_acceptances", user["token"], q)
    if not accepted:
        raise HTTPException(428, "최신 이용약관 확인 및 동의가 필요합니다.")
    return user

async def signup_preflight(terms_id: UUID, accepted: bool):
    terms = await published("terms")
    if not terms:
        raise HTTPException(503, "회원가입 전에 이용약관 게시가 필요합니다.")
    if not accepted or terms["doc_id"] != str(terms_id):
        raise HTTPException(409, "최신 이용약관을 읽고 동의해 주세요.")
    return terms

@router.get("/documents")
async def public_documents():
    return {"privacy":await published("privacy"), "terms":await published("terms"),
            "notice":"게시된 버전만 공식 문서로 표시됩니다. 미게시 초안은 공개되지 않습니다."}

@router.get("/acceptance")
async def acceptance_status(user=Depends(user_identity)):
    terms=await published("terms")
    if not terms:
        return {"required":True,"accepted":False,"terms":None}
    rows=await store.rows("rights_policy_acceptances",user["token"],
        "select=doc_id,accepted_at&doc_id=eq."+terms["doc_id"]+"&limit=1")
    return {"required":True,"accepted":bool(rows),"terms":{"doc_id":terms["doc_id"],"version":terms["version"]},
            "accepted_at":rows[0]["accepted_at"] if rows else None}

@router.post("/acceptance")
async def accept_terms(data: Acceptance, user=Depends(user_identity)):
    if not data.accepted:
        raise HTTPException(422,"약관 동의 여부를 확인하세요.")
    terms=await signup_preflight(data.terms_id,True)
    old=await store.rows("rights_policy_acceptances",user["token"],
        "select=doc_id&doc_id=eq."+terms["doc_id"]+"&limit=1")
    if not old:
        await store.insert("rights_policy_acceptances",user["token"],
            {"owner_id":user["id"],"doc_id":terms["doc_id"]})
    return {"accepted":True,"terms_version":terms["version"]}

@router.get("/admin")
async def admin_documents(user=Depends(admin_identity)):
    docs=await store.rows("rights_legal_documents",user["token"],"select=*&order=created_at.desc&limit=100")
    requests=await store.rows("rights_privacy_requests",user["token"],"select=request_id,owner_id,request_type,status,created_at&order=created_at.desc&limit=100")
    return {"documents":docs,"privacy_requests":requests}

@router.post("/admin",status_code=201)
async def new_document(data:DocumentDraft,user=Depends(admin_identity)):
    prior=await store.rows("rights_legal_documents",user["token"],
        "select=version&kind=eq."+data.kind+"&order=version.desc&limit=1")
    version=prior[0]["version"]+1 if prior else 1
    return (await store.insert("rights_legal_documents",user["token"],
        {"kind":data.kind,"version":version,"content":data.content,
         "effective_on":data.effective_on,"editor_id":user["id"],"status":"draft"}))[0]

@router.patch("/admin/{doc_id}")
async def edit_document(doc_id:UUID,data:DraftEdit,user=Depends(admin_identity)):
    query="doc_id=eq."+str(doc_id)+"&status=eq.draft&revision=eq."+str(data.revision)
    rows=await store.call("PATCH","/rest/v1/rights_legal_documents?"+query,user["token"],
        body={"content":data.content,"effective_on":data.effective_on},
        headers={"Prefer":"return=representation"})
    if not rows:
        raise HTTPException(409,"게시된 문서는 수정할 수 없거나 다른 변경이 반영됐습니다.")
    return rows[0]

@router.post("/admin/{doc_id}/publish")
async def publish_document(doc_id:UUID,data:PublishApproval,user=Depends(admin_identity)):
    if not all((data.verified_operator_contact,data.verified_retention_disposal,
                data.verified_vendors_transfers,data.reviewed_by_human)):
        raise HTTPException(422,"운영자 연락처·보존기간·위탁/국외이전·인간 검토 확인이 필요합니다.")
    current=await store.rows("rights_legal_documents",user["token"],
        "select=*&doc_id=eq."+str(doc_id)+"&limit=1")
    if not current or current[0]["status"]!="draft" or current[0]["revision"]!=data.revision:
        raise HTTPException(409,"초안 버전이 변경됐거나 이미 게시됐습니다.")
    doc=current[0]
    if any(x in doc["content"] for x in ("[확인 필요]","[작성 필요]","TODO","미확정","TBD")):
        raise HTTPException(422,"검토되지 않은 안내 문구가 남아 있습니다.")
    if doc["effective_on"]<datetime.now(timezone.utc).date().isoformat():
        raise HTTPException(422,"시행일을 과거로 소급할 수 없습니다.")
    if doc["kind"]=="privacy":
        required=("처리 목적","보유","파기","정보주체","연락처","위탁","국외")
    else:
        required=("서비스","권리","검사","계정","책임")
    if not all(x in doc["content"] for x in required):
        raise HTTPException(422,"필수 검토 항목이 누락됐습니다.")
    rows=await store.call("PATCH","/rest/v1/rights_legal_documents?doc_id=eq."+str(doc_id)+"&status=eq.draft&revision=eq."+str(data.revision),
        user["token"],body={"status":"published","published_at":datetime.now(timezone.utc).isoformat()},
        headers={"Prefer":"return=representation"})
    if not rows:
        raise HTTPException(409,"동시 변경이 감지됐습니다.")
    return {"published":True,"document":rows[0]}

@router.post("/privacy-requests",status_code=201)
async def request_privacy(data:PrivacyRequest,user=Depends(user_identity)):
    return (await store.insert("rights_privacy_requests",user["token"],
        {"owner_id":user["id"],"request_type":data.request_type}))[0]

@router.get("/privacy-requests")
async def privacy_requests(user=Depends(user_identity)):
    rows=await store.rows("rights_privacy_requests",user["token"],
        "select=request_id,request_type,status,created_at,resolved_at&order=created_at.desc&limit=100")
    return {"requests":rows,"notice":"요청 접수는 삭제·정정 처리 완료가 아닙니다."}

@router.get("/my-data")
async def my_data(user=Depends(user_identity)):
    # Metadata-only; original binary files are intentionally excluded.
    assets=await store.rows("rights_assets",user["token"],"select=*&order=created_at.desc&limit=500")
    keys=await store.rows("rights_connection_keys",user["token"],
        "select=key_id,label,scope,expires_at,revoked,created_at&limit=100")
    checks=await store.rows("rights_checks",user["token"],
        "select=check_id,asset_id,created_at,result&order=created_at.desc&limit=100")
    return {"account":{"id":user["id"],"email":user["email"]},
            "assets":assets,"connection_key_metadata":keys,"recent_checks":checks,
            "notice":"메타데이터 열람용입니다. 원본 파일 전체와 과거 검사기록 전체를 포함하지 않습니다. 완전한 열람은 별도 요청하세요."}
