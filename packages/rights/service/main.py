from __future__ import annotations
import hashlib,json,secrets,os,html
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote,urlsplit
from uuid import UUID,uuid4
from datetime import datetime,timezone,timedelta
from fastapi import FastAPI,HTTPException,Request,Depends,UploadFile,File
from fastapi.responses import JSONResponse,FileResponse,Response,HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
import store
from models import AssetInput,Login,CheckInput,KeyInput,Usage
from policy import evaluate,credits,LICENSES,LABELS,VERSION,DISCLAIMER,markdown_text
from uploads import validate_file,MAX_FILE
from remote import transport,AuthenticatedMCP
import legal

PUBLIC=Path(__file__).parent/'public'
@asynccontextmanager
async def lifespan(app):
    async with transport.router.lifespan_context(transport):yield
app=FastAPI(title='ALDOL RIGHTS',version=VERSION,lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
app.include_router(legal.router)

class Guard:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        h=dict(scope['headers']);path=scope['path'];method=scope['method']
        async def denied(status,message):
            await JSONResponse({'detail':message},status_code=status)(scope,receive,send)
        if path.startswith('/api/') and method not in ('GET','HEAD','OPTIONS'):
            origin=h.get(b'origin',b'').decode();host=h.get(b'host',b'').decode()
            if (origin and urlsplit(origin).netloc!=host) or h.get(b'x-rights-client')!=b'web':
                return await denied(403,'허용되지 않은 요청 출처입니다.')
        limit=MAX_FILE+1048576 if path.endswith('/upload') else 1048576
        body=[];size=0
        if method in ('POST','PUT','PATCH'):
            while True:
                msg=await receive()
                if msg['type']=='http.disconnect':return
                size+=len(msg.get('body',b''))
                if size>limit:return await denied(413,'요청 크기가 너무 큽니다.')
                body.append(msg)
                if not msg.get('more_body'):break
        async def recv():
            if body:return body.pop(0)
            return await receive()
        async def secure_send(msg):
            if msg['type']=='http.response.start':
                headers=list(msg.get('headers',[]))
                headers.extend([(b'x-content-type-options',b'nosniff'),(b'referrer-policy',b'no-referrer'),(b'x-frame-options',b'DENY'),(b'cache-control',b'no-store'),(b'permissions-policy',b'camera=(), microphone=(), geolocation=()'),(b'content-security-policy',b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")])
                msg['headers']=headers
            await send(msg)
        await self.app(scope,recv,secure_send)
app.add_middleware(Guard)

@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    return JSONResponse({'detail':'입력 형식·길이를 확인하세요. URL은 HTTPS, 비밀번호는 8자 이상이어야 합니다.','fields':['.'.join(str(x) for x in e['loc'][1:]) for e in exc.errors()]},status_code=422)

@app.exception_handler(Exception)
async def internal_error(request,exc):return JSONResponse({'detail':'요청 처리 중 오류가 발생했습니다. 잠시 후 다시 시도하세요.'},status_code=500)

def cookies(response,data):
    for name,key,age in [('rights_access','access_token',3600),('rights_refresh','refresh_token',30*86400)]:
        response.set_cookie(name,data[key],max_age=age,httponly=True,secure=os.getenv('RIGHTS_DEV')!='1',samesite='strict',path='/api')

async def identity(request:Request):
    token=request.cookies.get('rights_access','')
    if not token:raise HTTPException(401,'로그인이 필요합니다.')
    user=await store.call('GET','/auth/v1/user',token)
    if not user.get('id') or user.get('is_anonymous'):raise HTTPException(401,'정식 계정 로그인이 필요합니다.')
    return {'id':user['id'],'email':user.get('email',''),'token':token}

@app.get('/api/health')
async def health():return {'service':'ALDOL RIGHTS','version':VERSION,'legal_patch':'0.3.0-draft','transport':'Streamable HTTP','mcp_auth':'read-only bearer connection key','legal_clearance':False}

@app.get('/api/licenses')
async def licenses():return {'licenses':LICENSES,'labels':LABELS,'disclaimer':DISCLAIMER}

@app.post('/api/auth/login')
async def login(data:Login):
    result=await store.call('POST','/auth/v1/token?grant_type=password',body=data.model_dump())
    r=JSONResponse({'email':result['user'].get('email','')});cookies(r,result);return r

@app.post('/api/auth/signup')
async def signup(data:legal.SignupAgreement):
    await legal.signup_preflight(data.terms_id,data.terms_accepted)
    result=await store.call('POST','/auth/v1/signup',body={'email':data.email,'password':data.password})
    r=JSONResponse({'message':'가입 요청을 접수했습니다. 이메일 확인이 필요한 경우 받은 편지함을 확인하세요.'})
    if result.get('access_token'):cookies(r,result)
    return r

@app.post('/api/auth/refresh')
async def refresh(request:Request):
    token=request.cookies.get('rights_refresh')
    if not token:raise HTTPException(401,'다시 로그인하세요.')
    result=await store.call('POST','/auth/v1/token?grant_type=refresh_token',body={'refresh_token':token})
    r=JSONResponse({'ok':True});cookies(r,result);return r

@app.post('/api/auth/logout')
async def logout(request:Request):
    token=request.cookies.get('rights_access')
    if token:
        try:await store.call('POST','/auth/v1/logout?scope=local',token)
        except HTTPException:pass
    r=JSONResponse({'ok':True})
    for k in ('rights_access','rights_refresh'):r.delete_cookie(k,path='/api')
    return r

@app.get('/api/session')
async def session(user=Depends(identity)):return {'id':user['id'],'email':user['email']}

async def all_assets(user,project=''):
    data=await store.rows('rights_assets',user['token'],'select=*&order=created_at.desc&archived=eq.false&limit=501')
    if len(data)>500:raise HTTPException(413,'자산이 500개를 넘습니다. 전체 보고서를 생략할 수 없으므로 명시적 분할 검토가 필요합니다.')
    return [a for a in data if not project or a['project']==project]

async def one_asset(aid,user):
    data=await store.rows('rights_assets',user['token'],'select=*&asset_id=eq.'+str(aid))
    if not data:raise HTTPException(404,'자산을 찾을 수 없거나 접근 권한이 없습니다.')
    return data[0]

@app.get('/api/assets')
async def assets(user=Depends(identity)):return {'assets':await all_assets(user)}

@app.post('/api/assets')
async def register(data:AssetInput,user=Depends(legal.require_terms)):
    # Stable client UUID makes a retried registration idempotent.
    aid=str(data.asset_id)
    existing=await store.rows('rights_assets',user['token'],'select=*&asset_id=eq.'+aid)
    if existing:
        if any(existing[0].get(k)!=v for k,v in data.model_dump(mode='json').items()):
            raise HTTPException(409,'같은 등록 요청의 정보가 달라졌습니다. 저장된 자산에서 정보 수정을 이용하세요.')
        return existing[0]
    body=data.model_dump(mode='json');body['owner_id']=user['id']
    return (await store.insert('rights_assets',user['token'],body))[0]

@app.patch('/api/assets/{aid}')
async def update(aid:UUID,data:AssetInput,request:Request,user=Depends(legal.require_terms)):
    await one_asset(aid,user)
    rev=request.headers.get('if-match','')
    if not rev.isdigit() or str(aid)!=str(data.asset_id):raise HTTPException(409,'자산 버전을 새로 불러온 뒤 수정하세요.')
    body=data.model_dump(mode='json');body.pop('asset_id')
    result=await store.call('PATCH',f'/rest/v1/rights_assets?asset_id=eq.{aid}&revision=eq.{rev}',user['token'],body=body,headers={'Prefer':'return=representation'})
    if not result:raise HTTPException(409,'다른 수정이 반영됐습니다. 새로 불러오세요.')
    return result[0]

@app.get('/api/assets/{aid}')
async def detail(aid:UUID,user=Depends(identity)):
    a=await one_asset(aid,user)
    history=await store.rows('rights_checks',user['token'],f'select=*&asset_id=eq.{aid}&order=created_at.desc&limit=100')
    return {'asset':a,'history':history}

@app.post('/api/assets/{aid}/check')
async def check(aid:UUID,data:CheckInput,user=Depends(legal.require_terms)):
    a=await one_asset(aid,user)
    cid=str(data.check_id)
    existing=await store.rows('rights_checks',user['token'],'select=*&check_id=eq.'+cid)
    if existing:return existing[0]
    u=data.usage.model_dump()
    if a['usage']!=u:
        changed=await store.call('PATCH',f'/rest/v1/rights_assets?asset_id=eq.{aid}&revision=eq.{a["revision"]}',user['token'],body={'usage':u},headers={'Prefer':'return=representation'})
        if not changed:raise HTTPException(409,'사용 목적 저장 중 자산 정보가 변경됐습니다. 다시 확인하세요.')
        a=changed[0]
    result=evaluate(a,u)
    record={'check_id':cid,'owner_id':user['id'],'asset_id':str(aid),'asset_revision':a['revision'],'asset_snapshot':a,'usage':u,'result':result}
    return (await store.insert('rights_checks',user['token'],record))[0]

@app.get('/api/history')
async def history(user=Depends(identity)):
    return {'items':await store.rows('rights_checks',user['token'],'select=check_id,asset_id,asset_revision,result,created_at&order=created_at.desc&limit=100'),'limit':100}

@app.post('/api/assets/{aid}/upload')
async def upload(aid:UUID,request:Request,role:str='source',file:UploadFile=File(...),user=Depends(legal.require_terms)):
    a=await one_asset(aid,user)
    if role not in ('source','evidence'):raise HTTPException(422,'파일 역할을 확인하세요.')
    data=await file.read(MAX_FILE+1)
    try:mime=validate_file(file.filename or '',file.content_type,data)
    except ValueError as e:raise HTTPException(422,str(e))
    ext=Path(file.filename).suffix.lower();path=f"{user['id']}/{aid}/{uuid4().hex}{ext}"
    await store.call('POST','/storage/v1/object/rights-private/'+path,user['token'],content=data,headers={'Content-Type':mime,'x-upsert':'false'})
    result=await store.call('PATCH',f'/rest/v1/rights_assets?asset_id=eq.{aid}&revision=eq.{a["revision"]}',user['token'],body={role+'_path':path},headers={'Prefer':'return=representation'})
    if not result:raise HTTPException(409,'파일은 비공개로 저장됐으나 자산이 수정되어 연결에 실패했습니다. 새로 불러온 뒤 다시 연결하세요.')
    return result[0]

@app.get('/api/assets/{aid}/file')
async def download_file(aid:UUID,role:str='source',user=Depends(identity)):
    a=await one_asset(aid,user)
    if role not in ('source','evidence') or not a.get(role+'_path'):raise HTTPException(404,'파일이 없습니다.')
    path=a[role+'_path']
    if not path.startswith(user['id']+'/'+str(aid)+'/'):raise HTTPException(403,'접근이 거부됐습니다.')
    data=await store.call('GET','/storage/v1/object/authenticated/rights-private/'+path,user['token'])
    return Response(data,media_type='application/octet-stream',headers={'Content-Disposition':'attachment; filename="rights-asset'+Path(path).suffix+'"'})

@app.get('/api/keys')
async def keys(user=Depends(identity)):
    return {'keys':await store.rows('rights_connection_keys',user['token'],'select=key_id,label,expires_at,revoked,created_at,scope&order=created_at.desc')}

@app.post('/api/keys')
async def create_key(data:KeyInput,user=Depends(legal.require_terms)):
    token='ar_'+secrets.token_urlsafe(48)
    body={'key_id':str(uuid4()),'owner_id':user['id'],'label':data.label,'token_hash':hashlib.sha256(token.encode()).hexdigest(),'expires_at':(datetime.now(timezone.utc)+timedelta(days=data.days)).isoformat()}
    rows=await store.insert('rights_connection_keys',user['token'],body)
    return {'key_id':body['key_id'],'token':token,'scope':'rights:read','expires_at':body['expires_at'],'warning':'이 키는 한 번만 표시됩니다. ChatGPT의 인증 입력란에만 넣으세요.'}

@app.post('/api/keys/{kid}/revoke')
async def revoke(kid:UUID,user=Depends(identity)):
    result=await store.call('PATCH','/rest/v1/rights_connection_keys?key_id=eq.'+str(kid),user['token'],body={'revoked':True},headers={'Prefer':'return=representation'})
    if not result:raise HTTPException(404,'연결 키가 없습니다.')
    return {'revoked':True}

@app.get('/api/report')
async def report(project:str='',format:str='json',user=Depends(identity)):
    if len(project)>120:raise HTTPException(422,'프로젝트명이 너무 깁니다.')
    data=await all_assets(user,project)
    results=[evaluate(a,Usage(**a['usage']).model_dump()) for a in data]
    out={'version':VERSION,'project':project,'generated_at':datetime.now(timezone.utc).isoformat(),'count':len(data),'counts':{k:sum(r['decision']==k for r in results) for k in LABELS},'items':results,'credits':credits(data),'review_needed':[r['asset_id'] for r in results if r['decision']!='SUITABLE'],'legal_clearance':False,'disclaimer':DISCLAIMER}
    if format=='json':return out
    if format!='markdown':raise HTTPException(422,'지원하지 않는 보고서 형식입니다.')
    lines=['# ALDOL RIGHTS 프로젝트 점검표',f"생성: {out['generated_at']}",f'프로젝트: {markdown_text(project or "전체")}',DISCLAIMER,'']
    for r in results:
        lines.extend([f"## {markdown_text(r['title'])} — {r['status_label']}",f"라이선스: {r['license_id']} · 검사: {r['checked_at']}",f"신뢰 수준: {r['confidence']}"]+[f'- {x}' for x in r['basis']+r['blocked_reasons']+r['conditions']+r['missing_evidence']+r['human_review']]+[''])
    lines+=['## 저작자 표시 초안',out['credits']['credits']]
    return Response('\n'.join(lines),media_type='text/markdown; charset=utf-8',headers={'Content-Disposition':'attachment; filename="ALDOL-RIGHTS-report.md"'})

@app.get('/privacy',response_class=HTMLResponse)
async def public_privacy():
    return await public_legal_page('privacy')

@app.get('/terms',response_class=HTMLResponse)
async def public_terms():
    return await public_legal_page('terms')

async def public_legal_page(kind):
    doc=await legal.published(kind)
    if not doc:raise HTTPException(503,'공식 문서 게시 준비 중입니다.')
    title='개인정보처리방침' if kind=='privacy' else '서비스 이용약관'
    content=html.escape(doc['content'])
    return HTMLResponse('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+' | ALDOL RIGHTS</title><link rel="stylesheet" href="/static/style.css"></head><body><main><h1>'+title+'</h1><p>v'+str(doc['version'])+' · 시행일 '+html.escape(doc['effective_on'])+'</p><section class="card legal-document"><pre class="legal-content">'+content+'</pre></section><p><a href="/">ALDOL RIGHTS 홈으로 돌아가기</a></p></main></body></html>')

@app.get('/')
async def home():return FileResponse(PUBLIC/'index.html')
@app.get('/manifest.webmanifest')
async def manifest():return FileResponse(PUBLIC/'manifest.webmanifest',media_type='application/manifest+json')
app.mount('/static',StaticFiles(directory=PUBLIC),name='static')
app.mount('/',AuthenticatedMCP(transport))
