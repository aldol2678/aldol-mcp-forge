import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {randomUUID} from 'node:crypto';

const source=readFileSync(new URL('../../majung-studio/worker/runtime.mjs',import.meta.url),'utf8');
const toolSpecs=JSON.parse(readFileSync(new URL('../../majung-studio/worker/tools.json',import.meta.url),'utf8'));
const code=`const COMPANY="majung";const TOOLS=${JSON.stringify(toolSpecs)};const PAGE="";const CLIENT="";const CSS="";\n`+
 source.replace('export default {async fetch(req,env){','globalThis.__studio={async fetch(req,env){');
const env={MCP_BACKEND_TOKEN:'test-backend-token',MCP_BACKEND_URL:'https://majung-qa.example.workers.dev/mcp',MCP_BACKEND_ALLOWED_HOST:'majung-qa.example.workers.dev'};
const VERSION='2026-07-28';
const meta={'io.modelcontextprotocol/protocolVersion':VERSION,
 'io.modelcontextprotocol/clientCapabilities':{},
 'io.modelcontextprotocol/clientInfo':{name:'test-client',version:'2.0'}};
const fakeFetch=async (url,init)=>{
 const payload=JSON.parse(init.body);
 if(payload.method==='tools/list')return Response.json({jsonrpc:'2.0',id:payload.id,result:{resultType:'complete',tools:toolSpecs,cacheScope:'private',ttlMs:0}});
 return Response.json({jsonrpc:'2.0',id:payload.id,result:{resultType:'complete',content:[{type:'text',text:'{}'}],structuredContent:{recommendation:'HOLD',risks:'{}'},isError:false}});
};
const studio=runInNewContext(code+'\nglobalThis.__studio',{URL,Response,Request,TextDecoder,TextEncoder,Uint8Array,AbortSignal,crypto:{randomUUID},fetch:fakeFetch,btoa});
async function request(method,params={},modern=true,headers={}){
 const options={method:'POST',headers:{'content-type':'application/json',...(modern?{'MCP-Protocol-Version':VERSION,'Mcp-Method':method}:{}),...headers},
 body:JSON.stringify({jsonrpc:'2.0',id:3,method,params:modern?{...params,_meta:meta}:params})};
 const response=await studio.fetch(new Request('https://studio.example/mcp',options),env);
 return {status:response.status,body:await response.json()};
}
test('modern discover returns cacheable 2026 MCP envelope',async ()=>{
 const x=await request('server/discover');
 assert.equal(x.status,200);
 assert.equal(x.body.result.resultType,'complete');
 assert.deepEqual(Array.from(x.body.result.supportedVersions),[VERSION]);
 assert.equal(x.body.result.cacheScope,'private');
 assert.equal(x.body.result.ttlMs,0);
});
test('modern tools/list returns SDK v2 required metadata',async ()=>{
 const x=await request('tools/list');
 assert.equal(x.status,200);
 assert.equal(x.body.result.resultType,'complete');
 assert.equal(x.body.result.tools.length,3);
 assert.equal(x.body.result.cacheScope,'private');
});
test('modern tools/call forwards to configured backend',async ()=>{
 const x=await request('tools/call',{name:'evaluate_opportunity',arguments:{brief:'{}'}},true,{'Mcp-Name':'evaluate_opportunity'});
 assert.equal(x.status,200);
 assert.equal(x.body.result.resultType,'complete');
 assert.equal(x.body.result.structuredContent.recommendation,'HOLD');
});
test('modern header/name mismatch is rejected',async ()=>{
 const x=await request('tools/call',{name:'evaluate_opportunity',arguments:{brief:'{}'}},true,{'Mcp-Name':'research_market'});
 assert.equal(x.status,400);
 assert.equal(x.body.error.code,-32020);
});
test('old initialize and list remain available to existing Sites clients',async ()=>{
 const init=await request('initialize',{},false);
 const list=await request('tools/list',{},false);
 assert.equal(init.status,200);
 assert.equal(init.body.result.serverInfo.name,'ALDOL MAJUNG Studio');
 assert.equal(list.status,200);
 assert.equal(list.body.result.resultType,undefined);
});
