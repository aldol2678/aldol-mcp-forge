"""HTTP auth/protocol checks against an already running deployment."""
import json, os
import httpx2
url=os.environ['MCP_TEST_URL']
key=os.environ['UI_MCP_API_KEY']
base={'Authorization':'Bearer '+key,'Accept':'application/json, text/event-stream','Content-Type':'application/json'}
request={'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'security-test','version':'1'}}}
results=[]
with httpx2.Client(timeout=30) as c:
    cases=[('anonymous',{},json.dumps(request),401),('wrong_key',{'Authorization':'Bearer invalid'},json.dumps(request),401),
           ('malformed_json',base,'{',400),('body_limit',base,'x'*512001,413),
           ('untrusted_origin',{**base,'Origin':'https://evil.example'},json.dumps(request),403)]
    if url.startswith('http://127.'):
        cases.append(('host_rebinding',{**base,'Host':'evil.example'},json.dumps(request),421))
    for name,headers,body,status in cases:
        r=c.post(url,headers=headers,content=body)
        assert r.status_code==status,(name,r.status_code,r.text[:200])
        results.append({'test':name,'status':'PASS','http_status':r.status_code})
print(json.dumps({'results':results,'passed':len(results)},indent=2))
