"""New tool discovery, contracts and negative cases through the official MCP SDK."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdk_smoke import connection, data
from test_reference_visual import encoded


async def main():
    checks=[]
    async with connection() as s:
        tools=(await s.list_tools()).tools
        assert len(tools)==10
        checks.append('ten_tool_discovery')
        async def call(name,args,error=False):
            r=await s.call_tool(name,args)
            assert bool(r.is_error)==error,(name,error)
            checks.append(name + ('_safe_error' if error else '_success'))
            return None if error else data(r)
        r=await call('ui_reference_analyze',{'source':'<main><button>Save</button></main>'})
        assert r['status']=='DRAFT_REVIEW_REQUIRED'
        bridge=await call('ui_import_bonsae',{'bonsae_output_json':json.dumps(r['bonsae_spec_draft'])})
        spec=bridge['ui_spec_json']
        assert (await call('ui_validate',{'spec_json':spec}))['valid']
        for name in ('ui_generate','ui_audit','ui_review'): await call(name,{'spec_json':spec})
        for mode in ('layout','pixel','region'):
            out=await call('ui_visual_compare',{'reference_image':encoded(),'candidate_image':encoded(box=(60,20,120,80)), 'comparison_mode':mode,'viewport':'mobile'})
            assert out['changed_regions'] and out['diff_artifact']['data']
        out=await call('ui_visual_compare',{'reference_image':encoded(),'candidate_image':encoded()})
        assert out['pixel_difference']['ratio']==0
        out=await call('ui_visual_compare',{'reference_image':encoded(),'candidate_image':encoded(size=(161,120))})
        assert out['status']=='INCOMPARABLE'
        out=await call('ui_reference_analyze',{'source':''})
        assert out['status']=='INSUFFICIENT_EVIDENCE'
        out=await call('ui_reference_analyze',{'source':'<script>throw Error("PRIVATE_SENTINEL")</script><button>B</button>'})
        assert 'PRIVATE_SENTINEL' not in json.dumps(out)
        for args in ({'source':'{','source_format':'ui-json'}, {'source':'<div>'*100}, {'source':'x'*200001}, {'source':'a','source_format':'shell'}):
            await call('ui_reference_analyze',args,True)
        for args in ({'reference_image':'https://example.com/a.png','candidate_image':encoded()},
                     {'reference_image':'A'*240004,'candidate_image':encoded()},
                     {'reference_image':encoded(size=(4097,1),box=None),'candidate_image':encoded()},
                     {'reference_image':encoded(),'candidate_image':encoded(),'comparison_mode':'shell'}):
            await call('ui_visual_compare',args,True)
    print(json.dumps({'passed':len(checks),'checks':checks,'status':'PASS'},indent=2))


if __name__=='__main__': asyncio.run(main())
