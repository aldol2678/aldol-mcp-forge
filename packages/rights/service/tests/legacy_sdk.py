"""Exercise all original five stdio tools and SQLite persistence after restart."""
import asyncio,os,sys,tempfile,json
from pathlib import Path
from mcp.client.stdio import stdio_client,StdioServerParameters
from mcp.client import ClientSession
async def run():
    with tempfile.TemporaryDirectory() as tmp:
        p=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).resolve().parents[2]/'server.py')],env={**os.environ,'ALDOL_RIGHTS_DB':str(Path(tmp)/'test.sqlite3')})
        aid=None
        for cycle in (0,1):
            async with stdio_client(p) as (r,w):
                async with ClientSession(r,w) as s:
                    await s.initialize();listing=await s.list_tools();assert len(listing.tools)==5
                    if cycle==0:
                        o=await s.call_tool('register_asset',dict(title='Synthetic SDK fixture',kind='image',license_id='CC-BY-NC-4.0',creator='Author',source_url='https://example.org/source',evidence_url='https://example.org/license'))
                        assert not o.is_error
                        data=o.structured_content or json.loads(o.content[0].text);aid=data['asset_id']
                        for n,args in [('inspect_license',{'license_id':'CC-BY-4.0'}),('check_usage',{'asset_id':aid,'commercial':True}),('generate_credits',{}),('rights_report',{})]:
                            o=await s.call_tool(n,args);assert not o.is_error;print('legacy_stdio_'+n,'PASS',flush=True)
                    else:
                        o=await s.call_tool('check_usage',{'asset_id':aid,'commercial':True});data=o.structured_content or json.loads(o.content[0].text)
                        assert data['status']=='BLOCKED';print('legacy_stdio_restart_persistence PASS',flush=True)
asyncio.run(run())
