"""Unit contract checks for the isolated RIGHTS legal v0.3 endpoints."""
import sys
from pathlib import Path
from uuid import UUID
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
import legal
from main import app

client=TestClient(app)
TERMS_ID='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
HEADERS={'x-rights-client':'web'}

def test_signup_never_proceeds_without_published_policy(monkeypatch):
    async def missing(kind):return None
    monkeypatch.setattr(legal,'published',missing)
    r=client.post('/api/auth/signup',headers=HEADERS,json={
        'email':'sample@example.test','password':'testpass123',
        'terms_id':TERMS_ID,'terms_accepted':True})
    assert r.status_code==503

def test_declined_or_old_terms_rejected_before_auth(monkeypatch):
    async def current(kind):
        return {'doc_id':TERMS_ID,'kind':kind,'version':1} if kind=='terms' else {'doc_id':'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'}
    monkeypatch.setattr(legal,'published',current)
    body={'email':'sample@example.test','password':'testpass123',
          'terms_id':TERMS_ID,'terms_accepted':False}
    assert client.post('/api/auth/signup',headers=HEADERS,json=body).status_code==409
    body['terms_accepted']=True
    body['terms_id']='cccccccc-cccc-4ccc-8ccc-cccccccccccc'
    assert client.post('/api/auth/signup',headers=HEADERS,json=body).status_code==409

def test_policy_admin_fails_closed(monkeypatch):
    async def logged():return {'id':'12345678-1234-4234-8234-123456789012','email':'sample@example.test','token':'fixture'}
    async def no_admin(*args,**kwargs):return []
    app.dependency_overrides[legal.user_identity]=logged
    monkeypatch.setattr(legal.store,'rows',no_admin)
    try:
        assert client.get('/api/legal/admin').status_code==403
        assert client.post('/api/legal/admin',headers=HEADERS,json={
            'kind':'terms','content':'test'*101,'effective_on':'2026-11-01'}).status_code==403
    finally:app.dependency_overrides.clear()

def test_privacy_request_type_allowlist():
    # Invalid enumerations fail validation regardless of auth; never permit arbitrary operation names.
    result=client.post('/api/legal/privacy-requests',headers=HEADERS,json={'request_type':'delete_all_aram_users'})
    assert result.status_code in (401,422)

def test_public_draft_never_exposed(monkeypatch):
    async def none(*args,**kwargs):return []
    monkeypatch.setattr(legal.store,'rows',none)
    r=client.get('/api/legal/documents')
    assert r.status_code==200
    assert r.json()['terms'] is None and r.json()['privacy'] is None

def test_terms_gate_blocks_without_current_acceptance(monkeypatch):
    async def logged():return {'id':'12345678-1234-4234-8234-123456789012','email':'sample@example.test','token':'fixture'}
    async def current(kind):return {'doc_id':TERMS_ID,'version':2}
    async def no_acceptance(*args,**kwargs):return []
    app.dependency_overrides[legal.user_identity]=logged
    monkeypatch.setattr(legal,'published',current)
    monkeypatch.setattr(legal.store,'rows',no_acceptance)
    try:
        assert client.post('/api/assets',headers=HEADERS,json={
            'asset_id':TERMS_ID,'title':'test','kind':'image'}).status_code==428
    finally:app.dependency_overrides.clear()

def test_publish_validation_blocks_unverified_approval(monkeypatch):
    async def logged():return {'id':'12345678-1234-4234-8234-123456789012','email':'sample@example.test','token':'fixture'}
    async def admin_rows(*args,**kwargs):return [{'owner_id':'12345678-1234-4234-8234-123456789012'}]
    app.dependency_overrides[legal.user_identity]=logged
    monkeypatch.setattr(legal.store,'rows',admin_rows)
    try:
        r=client.post('/api/legal/admin/'+TERMS_ID+'/publish',headers=HEADERS,json={
            'revision':1,'verified_operator_contact':False,
            'verified_retention_disposal':True,'verified_vendors_transfers':True,
            'reviewed_by_human':True})
        assert r.status_code==422
    finally:app.dependency_overrides.clear()

def test_public_html_policy_escapes_untrusted_policy_text(monkeypatch):
    async def policy(kind):
        return {'kind':kind,'version':1,'effective_on':'2026-10-23',
                'content':'<script>alert("x")</script>\n'+'저작권 검토 참고 문구 '*25}
    monkeypatch.setattr(legal,'published',policy)
    r=client.get('/privacy')
    assert r.status_code==200
    assert '&lt;script&gt;' in r.text
    assert '<script>alert' not in r.text
    assert '개인정보처리방침' in r.text

def test_no_public_html_document_before_approval(monkeypatch):
    async def missing(kind):return None
    monkeypatch.setattr(legal,'published',missing)
    assert client.get('/terms').status_code==503
