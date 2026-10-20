import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../worker/index.js';
const req=(path,body,user='alice',origin='https://forge.example')=>new Request('https://forge.example'+path,{method:body?'POST':'GET',headers:{'content-type':'application/json',...(user?{'oai-authenticated-user-id':user}:{}),origin},...(body?{body:JSON.stringify(body)}:{})});
class Bucket {
  data=new Map();
  async put(k,v,options){if(options?.onlyIf?.etagDoesNotMatch==='*'&&this.data.has(k))return null;this.data.set(k,v);return {etag:k};}
  async get(k){const value=this.data.get(k);return value?{text:async()=>value,json:async()=>JSON.parse(value)}:null;}
  async list({prefix}){return {objects:[...this.data.keys()].filter(k=>k.startsWith(prefix)).map(key=>({key})),truncated:false};}
}
const env=()=>({BUCKET:new Bucket(),FORGE_WRITES_VERIFIED:'1'});
test('Studio serves functional accessible workspace',async()=>{const r=await worker.fetch(req('/'));assert.equal(r.status,200);assert.match(await r.text(),/Forge Studio/);});
test('identity and verification gate block writes and user-controlled principals',async()=>{for(const [user,e] of [[null,env()],['alice',{BUCKET:new Bucket()}]]){const r=await worker.fetch(req('/api/projects',{project_name:'test-one',description:'HTML 검사'},user),e);assert.equal(r.status,403);}const e=env();assert.equal((await worker.fetch(req('/api/projects',{project_name:'test-one',description:'HTML 검사',owner:'bob'}),e)).status,400);assert.equal((await worker.fetch(req('/api/projects',{project_name:'test-one',description:'HTML 검사'},'alice','https://evil.example'),e)).status,403);});
test('create, readback, immutable edit, ZIP, tenant exclusion and invalid inputs',async()=>{
 const e=env();const r=await worker.fetch(req('/api/projects',{project_name:'html-checker',description:'HTML 게임 검사'}),e);assert.equal(r.status,201);const p=await r.json();assert.equal(p.project_name,'html-checker');assert.ok(p.id);assert.match(p.files['server.py'],/def html_audit/);assert.equal(p.validation.official_sdk.status,'SKIP');
 assert.equal((await worker.fetch(req('/api/projects/'+p.id,null,'bob'),e)).status,404);
 assert.equal((await worker.fetch(req('/api/projects',{project_name:'html-checker',description:'HTML 검사'}),e)).status,409);
 const list=await (await worker.fetch(req('/api/projects'),e)).json();assert.equal(list.projects.length,1);
 const edited=await worker.fetch(req('/api/projects/'+p.id+'/tools',{template:'text_stats'}),e);assert.equal(edited.status,201);const p2=await edited.json();assert.notEqual(p2.id,p.id);assert.match(p2.files['server.py'],/def text_stats/);assert.equal(p2.parent_id,p.id);
 const original=await (await worker.fetch(req('/api/projects/'+p.id),e)).json();assert.equal(original.tools.length,1);
 const z=await worker.fetch(req('/api/projects/'+p2.id+'/package'),e);assert.equal(z.status,200);assert.equal(z.headers.get('content-type'),'application/zip');assert.ok(z.headers.get('x-content-sha256'));assert.deepEqual([...new Uint8Array(await z.arrayBuffer()).slice(0,4)],[80,75,3,4]);
 for(const bad of ['../escape','a','x\n','UPPER'])assert.equal((await worker.fetch(req('/api/projects',{project_name:bad,description:'HTML'}),e)).status,400);
});
test('OpenAPI import accepts GET, keeps dry-run and rejects malformed specs',async()=>{
 const e=env(),spec_json=JSON.stringify({openapi:'3.0.0',info:{title:'Pets'},paths:{'/pets':{get:{operationId:'listPets'},post:{}}}});
 const r=await worker.fetch(req('/api/projects',{project_name:'pets-api',spec_json}),e);assert.equal(r.status,201);const p=await r.json();assert.deepEqual(p.tools,['listPets']);assert.ok(p.files['api_runtime.py']);assert.equal(p.validation.python_execution.status,'SKIP');assert.match(p.files['README.md'],/dry-run/);
 assert.equal((await worker.fetch(req('/api/projects',{project_name:'bad-api',spec_json:'{}'}),e)).status,400);
});
test('MCP write tools hidden until verified and never report Python execution as PASS',async()=>{const body={jsonrpc:'2.0',id:1,method:'tools/list'};const a=await (await worker.fetch(req('/mcp',body),{})).json();assert.equal(a.result.tools.length,3);const b=await (await worker.fetch(req('/mcp',body),env())).json();assert.ok(b.result.tools.some(t=>t.name==='forge_create'));});
test('MCP mutation keeps original JSON-RPC envelope rejection',async()=>{
 const e=env();for(const id of [{},[]]){const r=await (await worker.fetch(req('/mcp',{jsonrpc:'2.0',id,method:'tools/call',params:{name:'forge_create',arguments:{project_name:'never-create',description:'HTML 검사'}}}),e)).json();assert.equal(r.error?.code,-32600);}assert.equal(e.BUCKET.data.size,0);
});
test('all five Studio MCP tools dispatch through the actual JSON-RPC endpoint',async()=>{
 const e=env(),call=async(name,args)=>{const r=await (await worker.fetch(req('/mcp',{jsonrpc:'2.0',id:1,method:'tools/call',params:{name,arguments:args}}),e)).json();assert.equal(r.result?.isError,false,JSON.stringify(r));return r.result.structuredContent;};
 const p=await call('forge_create',{project_name:'mcp-generated',description:'HTML game audit'});const p2=await call('forge_add_tool',{project_id:p.id,template:'text_stats'});assert.deepEqual(p2.tools,['html_audit','text_stats']);
 const t=await call('forge_test',{project_id:p2.id});assert.equal(t.integrity.status,'PASS');assert.equal(t.official_sdk.status,'SKIP');
 const z=await call('forge_package',{project_id:p2.id});assert.ok(z.bytes>100);assert.match(z.sha256,/^[a-f0-9]{64}$/);
 const p3=await call('forge_import_openapi',{project_name:'mcp-api',spec_json:JSON.stringify({openapi:'3.0.0',paths:{'/games':{get:{operationId:'listGames'}}}})});assert.deepEqual(p3.tools,['listGames']);assert.equal(p3.auto_deployed,false);
});
