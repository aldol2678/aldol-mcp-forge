import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from main import app
from uploads import validate_file
from models import AssetInput
from pydantic import ValidationError
import pytest

client=TestClient(app)

def test_private_routes_deny_missing_and_invalid_credentials():
    for path in ['/api/assets','/api/history','/api/keys','/api/report']:
        assert client.get(path).status_code==401
    r=client.post('/mcp',headers={'content-type':'application/json'},json={'jsonrpc':'2.0','method':'initialize','id':1})
    assert r.status_code==401 and 'Bearer' in r.headers['www-authenticate']

def test_csrf_and_request_size():
    assert client.post('/api/auth/login',headers={'Origin':'https://attacker.invalid','x-rights-client':'web'},json={}).status_code==403
    assert client.post('/api/assets',content='x'*1100000,headers={'x-rights-client':'web'}).status_code==413

def test_upload_signature_not_filename_or_client_mime():
    assert validate_file('proof.pdf','application/pdf',b'%PDF-1.4\ntest')=='application/pdf'
    with pytest.raises(ValueError): validate_file('proof.png','image/png',b'<script>alert(1)</script>')
    with pytest.raises(ValueError): validate_file('evil.svg','image/svg+xml',b'<svg/>')
    with pytest.raises(ValueError): validate_file('big.txt','text/plain',b'x'*(10485760+1))

def test_model_rejects_owner_override_and_credentials_in_url():
    data=dict(asset_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',title='a',kind='image')
    with pytest.raises(ValidationError):AssetInput(**data,owner_id='user2')
    with pytest.raises(ValidationError):AssetInput(**data,source_url='https://u:p@example.org')

def test_mcp_canonical_host_is_allowed_but_other_hosts_are_denied(monkeypatch):
    import store
    async def identity(*args,**kwargs):return {'owner_id':'fixture'}
    monkeypatch.setattr(store,'mcp_read',identity)
    message={'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'test','version':'1'}}}
    with TestClient(app) as c:
        headers={'Host':'rights.aldol.app','Authorization':'Bearer '+'x'*60,'Accept':'application/json, text/event-stream'}
        r=c.post('/mcp',headers=headers,json=message)
        assert r.status_code==200
        headers['Host']='attacker.invalid'
        assert c.post('/mcp',headers=headers,json=message).status_code==421
