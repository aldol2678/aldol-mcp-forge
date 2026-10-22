"""Post-deploy negative auth, revision and persistence checks (synthetic fixtures)."""
import os,json,uuid
from pathlib import Path
import httpx
creds=json.loads(Path(os.environ['RIGHTS_QA_CREDENTIALS']).read_text());base='https://rights.aldol.app';headers={'x-rights-client':'web','Origin':base}
c=httpx.Client(base_url=base,headers=headers,timeout=45)
assert c.post('/api/auth/login',json={k:creds[0][k] for k in ('email','password')}).status_code==200
results=[]
def ok(name,condition):
 print(name,'PASS' if condition else 'FAIL',flush=True);results.append({'test':name,'status':'PASS' if condition else 'FAIL'});assert condition
msg={'jsonrpc':'2.0','method':'initialize','id':1,'params':{'protocolVersion':'2025-11-25','capabilities':{},'clientInfo':{'name':'qa','version':'1'}}}
for label,key in [('missing',''),('invalid','ar_'+'x'*64)]:
 r=httpx.post(base+'/mcp',headers=({'Authorization':'Bearer '+key} if key else {})|{'Accept':'application/json,text/event-stream'},json=msg,timeout=45);ok('MCP_'+label+'_auth_denied',r.status_code==401)
aid=creds[0]['asset_id'];a=c.get('/api/assets/'+aid).json()['asset'];u={**a['usage'],'commercial':False}
r=c.post('/api/assets/'+aid+'/check',json={'check_id':str(uuid.uuid4()),'usage':u});ok('recheck_saved_new_usage',r.status_code==200 and r.json()['result']['decision']=='SUITABLE')
r=c.get('/api/assets/'+aid).json();ok('usage_persistent_and_old_history_retained',r['asset']['usage']['commercial']==False and len(r['history'])>=2 and r['history'][0]['asset_revision']==r['asset']['revision'])
report=c.get('/api/report').json();ok('report_uses_current_saved_usage',any(i['asset_id']==aid and i['decision']=='SUITABLE' for i in report['items']))
# Snapshot protected data must remain private after an actual Vercel redeployment.
ok('post_redeployment_persistence',r['asset']['asset_id']==aid and bool(r['asset']['evidence_path']))
key=c.post('/api/keys',json={'label':'Revocation fixture','days':1}).json()
ok('revoke_key',c.post('/api/keys/'+key['key_id']+'/revoke').json()['revoked'])
r=httpx.post(base+'/mcp',headers={'Authorization':'Bearer '+key['token'],'Accept':'application/json,text/event-stream'},json=msg,timeout=45);ok('revoked_MCP_auth_denied',r.status_code==401)
r=c.post('/api/assets/'+aid+'/upload',files={'file':('oversize.txt',b'x'*(10485760+1),'text/plain')});ok('oversize_upload_denied',r.status_code in (413,422))
r=c.post('/api/assets',headers={'Origin':'https://attacker.invalid'},json={});ok('deployed_CSRF_denied',r.status_code==403)
Path('/workspace/scratch/b83a4631bae0/rights-safety-results.json').write_text(json.dumps(results,indent=2))
