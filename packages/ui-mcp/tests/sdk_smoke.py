"""Real official MCP SDK smoke over stdio or authenticated HTTPS (no stubs)."""
import asyncio, json, os, sys
from pathlib import Path
from contextlib import asynccontextmanager
import httpx2
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
@asynccontextmanager
async def connection():
    url = os.environ.get('MCP_TEST_URL')
    if url:
        async with httpx2.AsyncClient(headers={'Authorization': 'Bearer '+os.environ['UI_MCP_API_KEY']}, timeout=30,
                                      trust_env=not url.startswith(('http://127.0.0.1:', 'http://localhost:'))) as http:
            async with streamable_http_client(url, http_client=http) as (r,w):
                async with ClientSession(r,w) as s:
                    await s.initialize(); yield s
    else:
        params=StdioServerParameters(command=sys.executable,args=['-m','ui_core.server'],cwd=str(ROOT))
        async with stdio_client(params) as (r,w):
            async with ClientSession(r,w) as s:
                await s.initialize(); yield s

def data(result):
    return result.structured_content or json.loads(result.content[0].text)

async def main():
    results=[]
    async with connection() as s:
        listed=await s.list_tools()
        names={t.name for t in listed.tools}
        assert names=={'ui_catalog','ui_validate','ui_audit','ui_review','ui_review_markup','ui_generate','ui_presets','ui_import_bonsae','ui_reference_analyze','ui_visual_compare'},names
        results.append({'test':'discovery_and_schemas','status':'PASS','tools':[t.model_dump(mode='json') for t in listed.tools]})
        async def call(name,args,label,check,error=False):
            r=await s.call_tool(name,args)
            assert bool(r.is_error)==error,(label,r)
            if not error: assert check(data(r)),(label,r)
            results.append({'test':label,'status':'PASS','isError':r.is_error})
            return r
        doc=json.loads((ROOT/'examples/web-dashboard.json').read_text())
        spec=json.dumps(doc,ensure_ascii=False)
        for name,args in [('ui_catalog',{}),('ui_presets',{}),('ui_validate',{'spec_json':spec}),('ui_audit',{'spec_json':spec}),('ui_review',{'spec_json':spec})]:
            await call(name,args,name,lambda d:bool(d))
        bonsae_fixture=json.dumps({'specification':json.dumps({
            'goal':'원정 상태', 'tokens':{'primary':'#E9B35E'},
            'components':[{'name':'Energy', 'role':'남은 에너지 표시',
                           'states':['default','loading','error'],
                           'mobile_behavior':'390px에서도 수치 표시',
                           'interaction':'실제 값은 호스트에서 공급'}],
            'layouts':{'390':'한 열','820':'두 열','1280':'세 열'},
            'motion':'reduced motion', 'accessibility':'레이블'},ensure_ascii=False),
            'constraints':json.dumps({'release_authorized':False})},ensure_ascii=False)
        await call('ui_import_bonsae',{'bonsae_output_json':bonsae_fixture},
                   'bonsae_handoff',lambda d:d['ui_validation']['valid'] and
                   d['status']=='HANDOFF_REVIEW_REQUIRED' and
                   d['release_authorized'] is False)
        await call('ui_import_bonsae',{'bonsae_output_json':'{}'},
                   'bonsae_bad_input',None,True)
        for v in ('0.1','0.2','0.3'):
            old=json.dumps({'version':v,'title':'저장','root':{'type':'button','label':'저장'}})
            await call('ui_validate',{'spec_json':old},'schema_'+v,lambda d:d['valid'])
        for target in ('web-html','game-hud-html','react-tsx'):
            await call('ui_generate',{'spec_json':spec,'target':target,'quality_mode':'enforce'},'generate_'+target,lambda d:bool(d))
        markup='<style>.a{border-left:3px solid red}.b{border-left:3px solid red}</style><h1>아이콘은 상태를 말한다.</h1>'
        await call('ui_review_markup',{'html_source':markup},'markup_three_high',lambda d:d['high_severity_count']==3)
        await call('ui_review_markup',{'html_source':'<h1>저장 내역</h1><p>아이콘은 상태를 말한다.</p>'},'normal_korean_body',lambda d:d['high_severity_count']==0)
        doc['root']['children'][1]['text']='아이콘은 상태를 말한다.'
        bad=json.dumps(doc,ensure_ascii=False)
        await call('ui_review',{'spec_json':bad},'review_violation',lambda d:d['high_severity_count']>=1)
        await call('ui_audit',{'spec_json':bad},'audit_violation',lambda d:bool(d))
        await call('ui_generate',{'spec_json':bad},'advisory_compatible',lambda d:bool(d))
        await call('ui_generate',{'spec_json':bad,'quality_mode':'enforce'},'enforce_blocks',None,True)
        doc['design']['exceptions']=[{'rule':'sloganized-declarative-headline','reason':'사전 검토한 브랜드 캠페인의 의도적 슬로건 사용'}]
        await call('ui_generate',{'spec_json':json.dumps(doc,ensure_ascii=False),'quality_mode':'enforce'},'reasoned_waiver',lambda d:bool(d))
        for name,args in [('ui_review',{'spec_json':'{'}),('ui_generate',{'spec_json':spec,'target':'shell'}),('ui_review_markup',{'html_source':'x'*120001}),('ui_review_markup',{'html_source':'','exceptions_json':'{'}),('ui_review',{'spec_json':'['*1100+'0'+']'*1100}),('ui_review',{'spec_json':123})]:
            await call(name,args,'invalid_'+str(len(results)),None,True)
        await call('ui_review_markup',{'html_source':'<script>fetch("http://127.0.0.1/secret")</script>'},'script_inspect_only',lambda d:d['context']=='markup')
    async with connection() as s:
        assert len((await s.list_tools()).tools)==10
        results.append({'test':'disconnect_reconnect','status':'PASS'})
    print(json.dumps({'sdk':'2.3.0','transport':'https' if os.environ.get('MCP_TEST_URL','').startswith('https:') else 'http' if os.environ.get('MCP_TEST_URL') else 'stdio','results':results,'passed':len(results)},ensure_ascii=False,indent=2))

if __name__=='__main__': asyncio.run(main())
