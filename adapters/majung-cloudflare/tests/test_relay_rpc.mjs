import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { randomUUID } from 'node:crypto';

const source = readFileSync(new URL('../../majung-studio/worker/runtime.mjs', import.meta.url), 'utf8');
const start = source.indexOf("const MCP_PROTOCOL=");
const end = source.indexOf("\nfunction unwrap(", start);
if (start < 0 || end < 0) throw Error('Modern relay RPC not found');
const snippet = source.slice(start, end);

async function simulate(method, params, asset=false, makeResponse=undefined) {
  const requests = [];
  const fakeFetch = async (url, options) => {
    requests.push({url, options});
    const body = JSON.parse(options.body);
    if (makeResponse) return makeResponse(body, options);
    return Response.json({jsonrpc:'2.0', id:body.id,
      result: asset?{content:[{type:'text',text:'legacy'}]}:
        {resultType:'complete',tools:[],content:[{type:'text',text:'{}'}],
         structuredContent:{ok:true},isError:false}
    });
  };
  const rpc = runInNewContext(snippet + '\nrpc', {
    fetch:fakeFetch, crypto:{randomUUID}, AbortSignal, Response,
    TextDecoder, TextEncoder, Uint8Array, btoa,
  });
  const value = await rpc('https://majung-test.workers.dev/mcp','synthetic-secret',method,params,asset);
  return {requests, value};
}

test('modern tools/list supplies mirrored method and protocol metadata', async () => {
  const {requests,value} = await simulate('tools/list');
  const req = requests[0].options;
  const body = JSON.parse(req.body);
  assert.equal(req.redirect,'manual');
  assert.equal(req.headers['MCP-Protocol-Version'],'2026-07-28');
  assert.equal(req.headers['Mcp-Method'],'tools/list');
  assert.equal(req.headers['Mcp-Name'],undefined);
  assert.equal(req.headers.Authorization,'Bearer synthetic-secret');
  assert.equal(body.params._meta['io.modelcontextprotocol/protocolVersion'],'2026-07-28');
  assert.deepEqual(body.params._meta['io.modelcontextprotocol/clientCapabilities'],{});
  assert.equal(body.params._meta['io.modelcontextprotocol/clientInfo'].name,'ALDOL MAJUNG Studio');
  assert.equal(value.resultType,'complete');
});

test('tools/call has an exact mirrored name and no mutation of input', async () => {
  const args={product:'{"name":"demo"}'};
  const params={name:'analyze_competitors', arguments:args};
  const {requests}=await simulate('tools/call',params);
  const req=requests[0].options;
  assert.equal(req.headers['Mcp-Name'],'analyze_competitors');
  assert.equal(JSON.parse(req.body).params.arguments.product,args.product);
  assert.equal(params._meta,undefined);
});

test('non-ASCII tool names use sentinel without header injection', async () => {
  const {requests}=await simulate('tools/call',{name:'조사',arguments:{}});
  assert.equal(requests[0].options.headers['Mcp-Name'],'=?base64?7KGw7IKs?=');
});

test('legacy Asset Factory call retains old headers and old parameters', async () => {
  const {requests}=await simulate('tools/call',{name:'audit_preview',arguments:{}},true);
  const req=requests[0].options;
  const body=JSON.parse(req.body);
  assert.equal(req.headers['OAI-Sites-Authorization'],'Bearer synthetic-secret');
  assert.equal(req.headers.Authorization,undefined);
  assert.equal(req.headers['MCP-Protocol-Version'],undefined);
  assert.equal(body.params._meta,undefined);
});

test('incomplete modern MCP envelope is not treated as a success', async () => {
  await assert.rejects(
    () => simulate('tools/list',{},false, body=>
      Response.json({jsonrpc:'2.0',id:body.id,result:{tools:[]}})),
    /최신 MCP 응답 계약/
  );
});

test('tool-reported errors do not become successful results', async () => {
  await assert.rejects(
    () => simulate('tools/call',{name:'research_market',arguments:{}},false, body=>
      Response.json({jsonrpc:'2.0',id:body.id,result:{
        resultType:'complete',isError:true,content:[{type:'text',text:'blocked'}]}})),
    /전문 도구/
  );
});

test('HTTP 3xx is rejected without following Location', async () => {
  await assert.rejects(
    () => simulate('tools/list',{},false,()=>
      new Response(null,{status:302,headers:{Location:'https://attacker.example/mcp'}})),
    /리다이렉트/
  );
});
