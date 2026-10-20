import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
import {parseContract, previewContract} from '../worker/contract.js';
import {generate,verifyProject,zipFiles} from '../worker/generator.js';
import worker from '../worker/index.js';

const ROOT=resolve(fileURLToPath(new URL('../../../',import.meta.url)));
const sample=name=>({name,description:'A read-only specialist tool. Not implemented.',
 inputs:[{name:'question',type:'string',required:true},{name:'limit',type:'integer',required:false}],
 output_schema:{type:'object',properties:{finding:{type:'string'}},required:['finding'],additionalProperties:false}});
const raw=name=>JSON.stringify({tools:[sample(name)]});
const req=(path,body,user='alice',origin='https://forge.example')=>new Request('https://forge.example'+path,{method:body?'POST':'GET',headers:{'content-type':'application/json',...(user?{'oai-authenticated-user-id':user}:{}),origin},...(body?{body:JSON.stringify(body)}:{})});
class Bucket {
 data=new Map();
 async put(k,v,options){if(options?.onlyIf?.etagDoesNotMatch==='*'&&this.data.has(k))return null;this.data.set(k,v);return {etag:k};}
 async get(k){const v=this.data.get(k);return v?{json:async()=>JSON.parse(v)}:null;}
 async list({prefix}){return {objects:[...this.data.keys()].filter(key=>key.startsWith(prefix)).map(key=>({key})),truncated:false};}
}
const env=()=>({BUCKET:new Bucket(),FORGE_WRITES_VERIFIED:'1'});

test('contract schema rejects duplicates, injected identifiers and nested output',()=>{
 assert.deepEqual(previewContract({contract_json:raw('audit_design')}).tools,['audit_design']);
 assert.throws(()=>parseContract('{"tools":[],"tools":[]}'),/Duplicate/);
 for(const name of ['app','__import__','a();exit()'])assert.throws(()=>parseContract(raw(name)),/Unsafe/);
 const bad=JSON.parse(raw('review_cost'));
 bad.tools[0].output_schema.properties.finding={type:'array'};
 assert.throws(()=>parseContract(JSON.stringify(bad)),/scalar types/);
 bad.tools[0].output_schema.properties.finding={type:'string'};
 bad.tools[0].inputs[0].description={type:'object'};
 assert.throws(()=>parseContract(JSON.stringify(bad)),/invalid field description/);
 const malicious=JSON.parse(raw('render_ui'));
 malicious.tools[0].description='"""\nimport os; os.system("touch /tmp/pwned")';
 assert.doesNotThrow(()=>parseContract(JSON.stringify(malicious)));
});

test('Sites generated source byte parity with trusted Python compiler',async()=>{
 const args={project_name:'seum-contract',contract_json:raw('analyze_code')};
 const p=await generate(args);
 assert.equal(p.kind,'declarative-scaffold');assert.equal(p.handlers_implemented,false);
 const py=[
  'import json,sys',
  'from contract_forge import parse_contract,render_server,readme',
  'data=json.loads(sys.stdin.read())',
  'contract=parse_contract(data["contract_json"])',
  'print(json.dumps({"server":render_server(data["project_name"],contract["tools"]),"readme":readme(data["project_name"],contract["tools"])},ensure_ascii=False))'
 ].join('\n');
 const python=spawnSync('python3',['-c',py],{input:JSON.stringify(args),encoding:'utf8',cwd:ROOT});
 assert.equal(python.status,0,python.stderr);
 const expected=JSON.parse(python.stdout);
 assert.equal(p.files['server.py'],expected.server);
 assert.equal(p.files['README.md'],expected.readme);
 assert.equal((await verifyProject(p)).integrity.status,'PASS');
 assert.deepEqual([...zipFiles(p.files).slice(0,4)],[80,75,3,4]);
 p.files['server.py']+='\n# tampered';
 assert.equal((await verifyProject(p)).integrity.status,'FAIL');
});

test('Sites authenticated immutable create/readback/test/ZIP and tenant isolation',async()=>{
 const e=env(),contract_json=raw('research_market');
 const preview=await worker.fetch(req('/api/contracts/preview',{contract_json}),e);
 assert.equal(preview.status,200);assert.equal((await preview.json()).handlers_implemented,false);
 assert.equal((await worker.fetch(req('/api/contracts/preview',{contract_json:raw('app')}),e)).status,400);
 assert.equal((await worker.fetch(req('/api/projects',{project_name:'majung-studio',contract_json},null),e)).status,403);
 assert.equal((await worker.fetch(req('/api/projects',{project_name:'majung-studio',contract_json},'alice','https://elsewhere.example'),e)).status,403);
 const created=await worker.fetch(req('/api/projects',{project_name:'majung-studio',contract_json}),e);
 assert.equal(created.status,201);const p=await created.json();
 assert.equal(p.kind,'declarative-scaffold');assert.equal(p.validation.official_sdk.status,'SKIP');
 assert.equal((await worker.fetch(req('/api/projects/'+p.id,null,'bob'),e)).status,404);
 assert.equal((await worker.fetch(req('/api/projects',{project_name:'majung-studio',contract_json}),e)).status,409);
 const list=await (await worker.fetch(req('/api/projects'),e)).json();
 assert.equal(list.projects.length,1);assert.equal(list.projects[0].contract_json,undefined);
 const v=await (await worker.fetch(req('/api/projects/'+p.id+'/test'),e)).json();
 assert.equal(v.integrity.status,'PASS');assert.equal(v.official_sdk.status,'SKIP');assert.equal(v.handlers_implemented,false);
 const z=await worker.fetch(req('/api/projects/'+p.id+'/package'),e);
 assert.equal(z.status,200);assert.match(z.headers.get('x-content-sha256'),/^[a-f0-9]{64}$/);
 assert.deepEqual([...new Uint8Array(await z.arrayBuffer()).slice(0,4)],[80,75,3,4]);
 assert.equal((await worker.fetch(req('/api/projects/'+p.id+'/tools',{template:'text_stats'}),e)).status,400);
 assert.equal((await worker.fetch(req('/api/draft',{project_name:'temporary-draft',contract_json}),{})).status,200);
});

test('MCP contract tools hidden until verified write gate',async()=>{
 const e=env(),message={jsonrpc:'2.0',id:1,method:'tools/list'};
 const hidden=await (await worker.fetch(req('/mcp',message),{})).json();
 assert.equal(hidden.result.tools.some(t=>t.name==='forge_create_contract'),false);
 const visible=await (await worker.fetch(req('/mcp',message),e)).json();
 assert.equal(visible.result.tools.some(t=>t.name==='forge_create_contract'),true);
 const call=async(name,args)=>(await (await worker.fetch(req('/mcp',{jsonrpc:'2.0',id:2,method:'tools/call',params:{name,arguments:args}}),e)).json()).result;
 const preview=await call('forge_preview_contract',{contract_json:raw('review_visual')});
 assert.equal(preview.structuredContent.count,1);
 const created=await call('forge_create_contract',{project_name:'bonsae-studio',contract_json:raw('review_visual')});
 assert.equal(created.structuredContent.handlers_implemented,false);
 const t=await call('forge_test',{project_id:created.structuredContent.id});
 assert.equal(t.structuredContent.integrity.status,'PASS');
 const zip=await call('forge_package',{project_id:created.structuredContent.id});
 assert.match(zip.structuredContent.sha256,/^[a-f0-9]{64}$/);
});

test('Studio browser client remains valid JavaScript with contract tab',()=>{
 const source=fileURLToPath(new URL('../worker/client.js',import.meta.url));
 const result=spawnSync(process.execPath,['--check',source],{encoding:'utf8'});
 assert.equal(result.status,0,result.stderr);
});
