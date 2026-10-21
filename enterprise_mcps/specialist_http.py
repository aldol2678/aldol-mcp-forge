"""Independent BONSAE/MAJUNG private HTTP runtime. SEUM runtime is untouched."""
from __future__ import annotations
import hmac
import os
import re
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from .server import create_app

MAX_BODY = 524288

class PrivateSpecialist:
    def __init__(self, inner, company, secret):
        self.inner, self.company, self.secret = inner, company, secret.encode()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.inner(scope, receive, send)
        path = scope.get('path', '')
        if path == '/healthz' and scope['method'] == 'GET':
            return await JSONResponse({'healthy': True, 'company': self.company})(scope, receive, send)
        if path not in ('/mcp', '/status'):
            return await JSONResponse({'error': 'not_found'}, status_code=404)(scope, receive, send)
        auth = [v for k,v in scope['headers'] if k.lower() == b'authorization']
        if len(auth) != 1 or not hmac.compare_digest(auth[0], b'Bearer ' + self.secret):
            return await JSONResponse({'error':'authorization_required'},status_code=401,
                headers={'cache-control':'no-store','www-authenticate':'Bearer'})(scope, receive, send)
        if path == '/status':
            return await JSONResponse({'company':self.company,'sdk':'2.0.0','authenticated':True,
                'source_commit':os.environ.get('RAILWAY_GIT_COMMIT_SHA', 'local'),
                'search_provider':os.environ.get('MAJUNG_SEARCH_PROVIDER','unconfigured') if self.company=='majung' else None},
                headers={'cache-control':'no-store'})(scope, receive, send)
        if scope['method'] != 'POST':
            return await JSONResponse({'error':'method_not_allowed'},status_code=405)(scope,receive,send)
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] != 'http.request':
                return
            body.extend(message.get('body', b''))
            if len(body) > MAX_BODY:
                return await JSONResponse({'error':'request_too_large'}, status_code=413)(scope,receive,send)
            if not message.get('more_body'):
                break
        consumed = False
        async def bounded_receive():
            nonlocal consumed
            if not consumed:
                consumed=True
                return {'type':'http.request','body':bytes(body),'more_body':False}
            return await receive()
        return await self.inner(scope, bounded_receive, send)

def create_http_app(company=None, secret=None, public_host=None):
    company = company or os.environ.get('ALDOL_COMPANY')
    secret = secret or os.environ.get('ALDOL_MCP_BEARER_TOKEN','')
    if company not in ('bonsae','majung'):
        raise RuntimeError('ALDOL_COMPANY must select bonsae or majung')
    if not 40 <= len(secret) <= 256 or not secret.isascii() or any(not 33<=ord(c)<=126 for c in secret):
        raise RuntimeError('Secure company-specific bearer secret required')
    host = public_host or os.environ.get('RAILWAY_PUBLIC_DOMAIN') or os.environ.get('ALDOL_PUBLIC_HOST')
    if host:
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?',host) or '..' in host:
            raise RuntimeError('Invalid public hostname')
        hosts=[host,host+':*']
        origins=['https://'+host]
    else:
        hosts=['127.0.0.1','127.0.0.1:*','localhost','localhost:*']
        origins=['http://127.0.0.1','http://localhost']
    inner=create_app(company).streamable_http_app(host='0.0.0.0',streamable_http_path='/mcp',
        json_response=True,stateless_http=True,max_request_body_size=MAX_BODY,
        transport_security=TransportSecuritySettings(allowed_hosts=hosts,allowed_origins=origins))
    return PrivateSpecialist(inner,company,secret)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(create_http_app(),host='0.0.0.0',port=int(os.environ.get('PORT','8080')),
                workers=1,log_level='warning',access_log=False)
