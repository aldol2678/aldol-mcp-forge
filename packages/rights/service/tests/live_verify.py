"""Explicit synthetic-fixture integration check. Never uses real user assets.
Usage: RIGHTS_QA_CREDENTIALS=/private/file python live_verify.py https://rights.aldol.app
Fixture file: [{id,email,password}, {id,email,password}]. No credentials in outputs.
"""
import os,sys,json,uuid,asyncio
from pathlib import Path
import httpx
BASE=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8012'
creds=json.loads(Path(os.environ['RIGHTS_QA_CREDENTIALS']).read_text())
HEAD={'x-rights-client':'web','Origin':BASE}
result=[]
def ok(name,condition):
    result.append({'test':name,'status':'PASS' if condition else 'FAIL'})
    print(name,result[-1]['status'],flush=True)
    if not condition:raise AssertionError(name)

def run():
    a=httpx.Client(base_url=BASE,timeout=60,headers=HEAD);b=httpx.Client(base_url=BASE,timeout=60,headers=HEAD)
    for i,c in enumerate([a,b]):
        r=c.post('/api/auth/login',json={k:creds[i][k] for k in ['email','password']})
        ok('web_login_'+str(i),r.status_code==200)
        if r.status_code!=200:print(r.text[:200]);return
    data=dict(asset_id=str(uuid.uuid4()),title='QA · '+('긴이름'*30),kind='image',license_id='CC-BY-NC-4.0',creator='Synthetic author',source_url='https://example.org/'+('a'*400),evidence_url='https://example.org/license',project='RIGHTS v0.2 synthetic QA',usage=dict(commercial=True,modified=False,redistribute=True,attribution_planned=True,derivative_license=''))
    aid=data['asset_id'];r=a.post('/api/assets',json=data);ok('asset_register',r.status_code==200)
    first=r.json();r=a.post('/api/assets',json=data);ok('registration_idempotency',r.status_code==200 and r.json()['asset_id']==aid)
    r=b.get('/api/assets/'+aid);ok('cross_user_read_denied',r.status_code==404)
    r=b.patch('/api/assets/'+aid,json=data,headers={'If-Match':'1'});ok('cross_user_edit_denied',r.status_code==404)
    cid=str(uuid.uuid4());payload={'check_id':cid,'usage':data['usage']}
    r=a.post('/api/assets/'+aid+'/check',json=payload);ok('check_conflict_saved',r.status_code==200 and r.json()['result']['decision']=='CONFLICT')
    r=a.post('/api/assets/'+aid+'/check',json=payload);ok('check_retry_idempotency',r.status_code==200 and r.json()['check_id']==cid)
    r=a.post('/api/assets/'+aid+'/upload?role=evidence',files={'file':('proof.pdf',b'%PDF-1.4\nSynthetic fixture','application/pdf')});ok('private_file_upload',r.status_code==200)
    path=r.json()['evidence_path']
    r=a.get('/api/assets/'+aid+'/file?role=evidence');ok('private_file_download',r.status_code==200 and r.content.startswith(b'%PDF-'))
    ok('cross_user_file_denied',b.get('/api/assets/'+aid+'/file?role=evidence').status_code==404)
    r=a.post('/api/assets/'+aid+'/upload',files={'file':('fake.png',b'<script>bad</script>','image/png')});ok('fake_mime_denied',r.status_code==422)
    for fmt in ['json','markdown']:
        r=a.get('/api/report',params={'project':data['project'],'format':fmt});ok('report_'+fmt,r.status_code==200 and ('CONFLICT' in r.text if fmt=='json' else '조건 충돌' in r.text))
    r=a.post('/api/keys',json={'label':'Synthetic QA','days':1});ok('read_key_issue',r.status_code==200)
    key=r.json();creds[0]['mcp_key']=key['token'];creds[0]['key_id']=key['key_id'];creds[0]['asset_id']=aid;creds[0]['file_path']=path
    r=b.post('/api/keys',json={'label':'Synthetic QA other owner','days':1});ok('other_read_key_issue',r.status_code==200)
    creds[1]['mcp_key']=r.json()['token'];creds[1]['key_id']=r.json()['key_id']
    Path(os.environ['RIGHTS_QA_CREDENTIALS']).write_text(json.dumps(creds))
    new=httpx.Client(base_url=BASE,headers=HEAD,timeout=60);new.cookies.update(a.cookies)
    ok('persistent_new_http_client',any(x['asset_id']==aid for x in new.get('/api/assets').json()['assets']))
    # Direct Data API must enforce RLS, not just the web API.
    supabase='https://aettjhzcmifjijxkwnmb.supabase.co';publishable='sb_publishable__PFuMnW_CbnL7ApIi1nzuw_0xXuARvd'
    with httpx.Client(timeout=30) as c:
        auth=c.post(supabase+'/auth/v1/token?grant_type=password',headers={'apikey':publishable},json={k:creds[1][k] for k in ('email','password')}).json()['access_token']
        r=c.get(supabase+'/rest/v1/rights_assets?asset_id=eq.'+aid,headers={'apikey':publishable,'Authorization':'Bearer '+auth});ok('direct_RLS_read_denied',r.status_code==200 and r.json()==[])
        r=c.patch(supabase+'/rest/v1/rights_assets?asset_id=eq.'+aid,headers={'apikey':publishable,'Authorization':'Bearer '+auth,'Prefer':'return=representation'},json={'title':'attack'});ok('direct_RLS_update_denied',r.status_code==200 and r.json()==[])
        r=c.get(supabase+'/storage/v1/object/public/rights-private/'+path);ok('public_file_url_denied',r.status_code>=400)
        r=c.post(supabase+'/rest/v1/rpc/rights_mcp_read',headers={'apikey':publishable},json={'p_token':creds[1]['mcp_key'],'p_action':'assets','p_ids':[aid]});ok('MCP_DB_cross_owner_denied',r.status_code>=400)
    outfile=Path(os.environ.get('RIGHTS_QA_RESULTS','/workspace/scratch/b83a4631bae0/rights-live-results.json'));outfile.write_text(json.dumps(result,ensure_ascii=False,indent=2));print('RESULTS',len(result),flush=True)
if __name__=='__main__':run()
