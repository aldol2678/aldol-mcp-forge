"""Private Streamable HTTP deployment; credentials stay outside the repository."""
from __future__ import annotations
import hmac
import os
from starlette.responses import JSONResponse
from mcp.server.transport_security import TransportSecuritySettings
from .server import app as mcp

class PrivateEndpoint:
    def __init__(self, app, token: str):
        if len(token) < 32:
            raise ValueError('UI_MCP_API_KEY must contain at least 32 characters')
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])
        if scope['path'] == '/health' and scope['method'] == 'GET':
            return await JSONResponse({'status': 'ok', 'service': 'aldol-ui-mcp', 'version': '0.3.2'})(scope, receive, send)
        supplied = headers.get(b'authorization', b'')
        expected = ('Bearer ' + self.token).encode()
        if not hmac.compare_digest(supplied, expected):
            return await JSONResponse({'error': 'unauthorized'}, status_code=401,
                                      headers={'WWW-Authenticate': 'Bearer', 'Cache-Control': 'no-store'})(scope, receive, send)
        return await self.app(scope, receive, send)

def create_app():
    hosts = ['127.0.0.1:*', 'localhost:*']
    domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
    if domain:
        hosts.extend([domain, domain + ':*'])
    inner = mcp.streamable_http_app(
        json_response=True, stateless_http=True, max_request_body_size=512_000,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=[]))
    return PrivateEndpoint(inner, os.environ.get('UI_MCP_API_KEY', ''))

def main():
    import uvicorn
    uvicorn.run(create_app(), host='0.0.0.0', port=int(os.environ.get('PORT', '8000')),
                log_level='info', access_log=False)

if __name__ == '__main__':
    main()
