"""Official SDK integration against the deployed MCP. Synthetic credentials only."""
import os,json,asyncio,sys
from pathlib import Path
import httpx2
from mcp.client import ClientSession
from mcp.client.streamable_http import streamable_http_client
creds=json.loads(Path(os.environ['RIGHTS_QA_CREDENTIALS']).read_text())
base=sys.argv[1] if len(sys.argv)>1 else 'https://rights.aldol.app'
async def run():
    outcomes=[]
    for i in (0,1):
        async with httpx2.AsyncClient(headers={'Authorization':'Bearer '+creds[i]['mcp_key']},timeout=60) as hc:
            async with streamable_http_client(base+'/mcp',http_client=hc) as (r,w):
                async with ClientSession(r,w,read_timeout_seconds=60) as s:
                    init=await s.initialize();outcomes.append(dict(test=f'initialize_user_{i}',status='PASS',protocol=init.protocol_version));print(outcomes[-1],flush=True)
                    listing=await s.list_tools();names=[t.name for t in listing.tools];assert len(names)==6 and 'register_asset' not in names;print('tools',names,flush=True);outcomes.append(dict(test=f'tools_list_user_{i}',status='PASS'))
                    calls=[('inspect_license',{'license_id':'CC-BY-4.0'}),('list_assets',{}),('check_usage',{'asset_id':creds[0]['asset_id'],'commercial':True,'attribution_planned':True}),('generate_credits',{}),('rights_report',{'project':'RIGHTS v0.2 synthetic QA'}),('review_history',{})]
                    for name,args in calls:
                        out=await s.call_tool(name,args)
                        denied=(i==1 and name=='check_usage')
                        assert bool(out.is_error)==denied,(name,out)
                        outcomes.append(dict(test=f'{name}_user_{i}',status='PASS',expected_denial=denied));print(outcomes[-1],flush=True)
    Path('/workspace/scratch/b83a4631bae0/rights-mcp-results.json').write_text(json.dumps(outcomes,indent=2))
asyncio.run(run())
