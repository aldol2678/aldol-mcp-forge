"""Supabase HTTPS adapter; only publishable key plus per-request user credential."""
import os
from fastapi import HTTPException
import httpx

URL=os.getenv('SUPABASE_URL','https://aettjhzcmifjijxkwnmb.supabase.co').rstrip('/')
KEY=os.getenv('SUPABASE_PUBLISHABLE_KEY','sb_publishable__PFuMnW_CbnL7ApIi1nzuw_0xXuARvd')

async def call(method,path,token=None,body=None,content=None,headers=None):
    h={'apikey':KEY}
    if token:h['Authorization']='Bearer '+token
    if headers:h.update(headers)
    try:
        async with httpx.AsyncClient(timeout=25,verify=True) as c:
            r=await c.request(method,URL+path,headers=h,json=body,content=content)
    except httpx.HTTPError:
        raise HTTPException(503,'연결이 지연됩니다. 잠시 후 다시 시도하세요.')
    if r.status_code>=400:
        status=401 if r.status_code in (401,403) else 409 if r.status_code==409 else 400 if r.status_code<500 else 503
        raise HTTPException(status,'인증 또는 접근 권한을 확인하세요.' if status==401 else '요청을 처리할 수 없습니다. 입력값과 연결 상태를 확인하세요.')
    if not r.content:return None
    if 'application/json' in r.headers.get('content-type',''):return r.json()
    return r.content

async def rows(table,token,query=''):
    return await call('GET','/rest/v1/'+table+'?'+query,token)

async def insert(table,token,data):
    return await call('POST','/rest/v1/'+table,token,body=data,headers={'Prefer':'return=representation'})

async def mcp_read(token,action='identity',ids=None):
    try:return await call('POST','/rest/v1/rpc/rights_mcp_read',body={'p_token':token,'p_action':action,'p_ids':ids})
    except HTTPException as e:
        if e.status_code!=503:raise HTTPException(401 if action=='identity' else 404,'연결 키 또는 자산 접근 권한을 확인하세요.')
        raise
