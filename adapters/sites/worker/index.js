import { core, readBounded, json } from './core.js';
import { SOURCE_SHA, generate, verifyProject } from './generator.js';
import { previewContract } from './contract.js';
import { writable, subject, requireWrite, listProjects, getProject, createProject, addTool, packageProject } from './store.js';
import { PAGE, CLIENT, CSS } from './page.js';
const extraTools=[
 {name:'forge_create',description:'Create and save an immutable curated Python MCP project in your Sites workspace; no execution or deployment.',inputSchema:{type:'object',properties:{project_name:{type:'string',pattern:'^[a-z][a-z0-9-]{2,39}$'},description:{type:'string',minLength:1,maxLength:2000}},required:['project_name','description'],additionalProperties:false}},
 {name:'forge_add_tool',description:'Add a curated tool as a new immutable project version. Existing version is preserved.',inputSchema:{type:'object',properties:{project_id:{type:'string'},template:{type:'string',enum:['html_audit','json_audit','text_stats']}},required:['project_id','template'],additionalProperties:false}},
 {name:'forge_test',description:'Verify stored file checksums only. Python execution and official SDK tests are SKIP on Sites.',inputSchema:{type:'object',properties:{project_id:{type:'string'}},required:['project_id'],additionalProperties:false}},
 {name:'forge_package',description:'Build an actual ZIP with SHA-256 and a private download path. No deployment.',inputSchema:{type:'object',properties:{project_id:{type:'string'}},required:['project_id'],additionalProperties:false}},
 {name:'forge_import_openapi',description:'Generate and save an OpenAPI GET-only Python MCP project, dry-run by default; Python execution SKIP.',inputSchema:{type:'object',properties:{project_name:{type:'string',pattern:'^[a-z][a-z0-9-]{2,39}
];
function validateExtra(tool,args){if(!args||typeof args!=='object'||Array.isArray(args)||Object.keys(args).some(k=>!Object.hasOwn(tool.inputSchema.properties,k))||tool.inputSchema.required.some(k=>typeof args[k]!=='string'))throw Error('필수 입력 또는 입력 형식을 확인해 주세요.');}
const secure={'cache-control':'no-store','x-content-type-options':'nosniff','referrer-policy':'same-origin'};
const textResponse=(s,type)=>new Response(s,{headers:{...secure,'content-type':type}});
export default {
 async fetch(request,env={}){
 const url=new URL(request.url),path=url.pathname;
 if(path==='/studio.js'&&request.method==='GET')return textResponse(CLIENT,'text/javascript; charset=utf-8');
 if(path==='/studio.css'&&request.method==='GET')return textResponse(CSS,'text/css; charset=utf-8');
 if(path==='/'&&request.method==='GET')return new Response(PAGE,{headers:{...secure,'content-type':'text/html; charset=utf-8','content-security-policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'self' https://chatgpt.com"}});
 if(path==='/mcp'){
  // Log only presence, never identity, prompts, specs, tokens or generated files.
  console.log(JSON.stringify({event:'forge-identity-boundary',authenticated:!!request.headers.get('oai-authenticated-user-id'),writes_enabled:writable(env)}));
  if(request.method!=='POST'||!writable(env))return core.fetch(request);
  let msg;try{msg=JSON.parse(await readBounded(request.clone()));}catch{return core.fetch(request);}
  if(msg?.jsonrpc!=='2.0'||!Object.hasOwn(msg,'id')||!['tools/list','tools/call'].includes(msg.method))return core.fetch(request);
  const base=await core.fetch(request.clone());if(base.status!==200)return base;const standard=await base.clone().json();if(standard.error&&msg.method!=='tools/call')return base;
  if(msg.method==='tools/list'){if(!standard.result)return base;standard.result.tools.push(...extraTools.map(t=>({...t,annotations:{readOnlyHint:['forge_test','forge_package','forge_preview_contract'].includes(t.name),destructiveHint:false,openWorldHint:false}})));return json(standard);}
  const tool=extraTools.find(t=>t.name===msg.params?.name);if(!tool)return base;
  try{subject(request);validateExtra(tool,msg.params.arguments);const a=msg.params.arguments;let output;
   if(['forge_create','forge_import_openapi','forge_create_contract'].includes(tool.name))output=await createProject(request,env,a);
   if(tool.name==='forge_preview_contract')output=previewContract(a);
   if(tool.name==='forge_add_tool')output=await addTool(request,env,a.project_id,{template:a.template});
   if(tool.name==='forge_test')output=await verifyProject(await getProject(request,env,a.project_id));
   if(tool.name==='forge_package'){const p=await getProject(request,env,a.project_id),pkg=await packageProject(p);output={project_id:p.id,sha256:pkg.sha256,bytes:pkg.bytes.length,download_path:'/api/projects/'+p.id+'/package',python_execution:'SKIP'};}
   return json({jsonrpc:'2.0',id:msg.id,result:{content:[{type:'text',text:JSON.stringify(output)}],structuredContent:output,isError:false}});
  }catch(e){return json({jsonrpc:'2.0',id:msg.id,result:{isError:true,content:[{type:'text',text:e.message}]}});}
 }
 if(!path.startsWith('/api/'))return json({error:'Not found'},404);
 try{
  if(path==='/api/session'&&request.method==='GET')return json({authenticated:!!request.headers.get('oai-authenticated-user-id'),writes_enabled:writable(env)&&!!request.headers.get('oai-authenticated-user-id'),storage:env.BUCKET?'R2':'unavailable',local_qa:env.LOCAL_QA===true,source_sha:SOURCE_SHA,version:'0.3.0-studio',python_execution:'SKIP',sdk:'UNKNOWN'});
  if(request.method==='POST'){
   if(request.headers.get('origin')!==url.origin)throw Object.assign(Error('동일한 사이트에서만 요청할 수 있습니다.'),{status:403});
   if(!(request.headers.get('content-type')||'').startsWith('application/json'))throw Error('JSON 형식으로 입력해 주세요.');
  }
  if(path==='/api/contracts/preview'&&request.method==='POST'){const a=JSON.parse(await readBounded(request));if(!a||typeof a!=='object'||Array.isArray(a)||Object.keys(a).length!==1||typeof a.contract_json!=='string')throw Error('contract_json 문자열만 입력해 주세요.');return json(previewContract(a));}
  if(path==='/api/rpc'&&request.method==='POST'){
   // Browser UI invokes the same three actual MCP handlers and response contract.
   const body=await readBounded(request);const r=await core.fetch(new Request(url.origin+'/mcp',{method:'POST',headers:{'content-type':'application/json'},body}));return r;
  }
  if(path==='/api/draft'&&request.method==='POST'){
   const args=JSON.parse(await readBounded(request));if(!args||typeof args!=='object'||Array.isArray(args))throw Error('입력은 JSON 객체여야 합니다.');if(Object.keys(args).some(k=>!['project_name','description','spec_json','contract_json'].includes(k)))throw Error('허용되지 않은 입력입니다.');if(['description','spec_json','contract_json'].filter(k=>Object.hasOwn(args,k)).length!==1)throw Error('설명·OpenAPI·도구 계약 JSON 중 하나만 입력해 주세요.');const p=await generate(args);return json({...p,saved:false});
  }
  if(path==='/api/projects'){
   if(request.method==='GET')return json(await listProjects(request,env));
   if(request.method==='POST'){requireWrite(request,env);return json(await createProject(request,env,JSON.parse(await readBounded(request))),201);}
   return json({error:'지원하지 않는 요청 방식입니다.'},405);
  }
  const m=path.match(/^\/api\/projects\/([a-f0-9-]+)(?:\/(tools|test|package))?$/);if(!m)return json({error:'Not found'},404);
  if(request.method==='POST'&&m[2]==='tools')return json(await addTool(request,env,m[1],JSON.parse(await readBounded(request))),201);
  if(request.method!=='GET')return json({error:'지원하지 않는 요청 방식입니다.'},405);
  const p=await getProject(request,env,m[1]);if(!m[2])return json(p);if(m[2]==='test')return json(await verifyProject(p));
  if(m[2]==='package'){const pkg=await packageProject(p);return new Response(pkg.bytes,{headers:{...secure,'content-type':'application/zip','content-disposition':`attachment; filename="${p.project_name}-${p.id.slice(0,8)}.zip"`,'x-content-sha256':pkg.sha256}});}
  return json({error:'Not found'},404);
 }catch(e){return json({error:e instanceof SyntaxError?'JSON 형식이 올바르지 않습니다. 괄호·따옴표를 확인해 주세요.':e.message},e.status||400);}
 }
};
},spec_json:{type:'string',minLength:2,maxLength:120000}},required:['project_name','spec_json'],additionalProperties:false}},
 {name:'forge_preview_contract',description:'Validate a custom declarative tool contract. No files created.',inputSchema:{type:'object',properties:{contract_json:{type:'string',minLength:2,maxLength:120000}},required:['contract_json'],additionalProperties:false}},
 {name:'forge_create_contract',description:'Generate and save an unimplemented Python MCP SDK scaffold from a JSON contract; no execution or deployment.',inputSchema:{type:'object',properties:{project_name:{type:'string',pattern:'^[a-z][a-z0-9-]{2,39}
];
function validateExtra(tool,args){if(!args||typeof args!=='object'||Array.isArray(args)||Object.keys(args).some(k=>!Object.hasOwn(tool.inputSchema.properties,k))||tool.inputSchema.required.some(k=>typeof args[k]!=='string'))throw Error('필수 입력 또는 입력 형식을 확인해 주세요.');}
const secure={'cache-control':'no-store','x-content-type-options':'nosniff','referrer-policy':'same-origin'};
const textResponse=(s,type)=>new Response(s,{headers:{...secure,'content-type':type}});
export default {
 async fetch(request,env={}){
 const url=new URL(request.url),path=url.pathname;
 if(path==='/studio.js'&&request.method==='GET')return textResponse(CLIENT,'text/javascript; charset=utf-8');
 if(path==='/studio.css'&&request.method==='GET')return textResponse(CSS,'text/css; charset=utf-8');
 if(path==='/'&&request.method==='GET')return new Response(PAGE,{headers:{...secure,'content-type':'text/html; charset=utf-8','content-security-policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'self' https://chatgpt.com"}});
 if(path==='/mcp'){
  // Log only presence, never identity, prompts, specs, tokens or generated files.
  console.log(JSON.stringify({event:'forge-identity-boundary',authenticated:!!request.headers.get('oai-authenticated-user-id'),writes_enabled:writable(env)}));
  if(request.method!=='POST'||!writable(env))return core.fetch(request);
  let msg;try{msg=JSON.parse(await readBounded(request.clone()));}catch{return core.fetch(request);}
  if(msg?.jsonrpc!=='2.0'||!Object.hasOwn(msg,'id')||!['tools/list','tools/call'].includes(msg.method))return core.fetch(request);
  const base=await core.fetch(request.clone());if(base.status!==200)return base;const standard=await base.clone().json();if(standard.error&&msg.method!=='tools/call')return base;
  if(msg.method==='tools/list'){if(!standard.result)return base;standard.result.tools.push(...extraTools.map(t=>({...t,annotations:{readOnlyHint:['forge_test','forge_package'].includes(t.name),destructiveHint:false,openWorldHint:false}})));return json(standard);}
  const tool=extraTools.find(t=>t.name===msg.params?.name);if(!tool)return base;
  try{subject(request);validateExtra(tool,msg.params.arguments);const a=msg.params.arguments;let output;
   if(tool.name==='forge_create'||tool.name==='forge_import_openapi')output=await createProject(request,env,a);
   if(tool.name==='forge_add_tool')output=await addTool(request,env,a.project_id,{template:a.template});
   if(tool.name==='forge_test')output=await verifyProject(await getProject(request,env,a.project_id));
   if(tool.name==='forge_package'){const p=await getProject(request,env,a.project_id),pkg=await packageProject(p);output={project_id:p.id,sha256:pkg.sha256,bytes:pkg.bytes.length,download_path:'/api/projects/'+p.id+'/package',python_execution:'SKIP'};}
   return json({jsonrpc:'2.0',id:msg.id,result:{content:[{type:'text',text:JSON.stringify(output)}],structuredContent:output,isError:false}});
  }catch(e){return json({jsonrpc:'2.0',id:msg.id,result:{isError:true,content:[{type:'text',text:e.message}]}});}
 }
 if(!path.startsWith('/api/'))return json({error:'Not found'},404);
 try{
  if(path==='/api/session'&&request.method==='GET')return json({authenticated:!!request.headers.get('oai-authenticated-user-id'),writes_enabled:writable(env)&&!!request.headers.get('oai-authenticated-user-id'),storage:env.BUCKET?'R2':'unavailable',local_qa:env.LOCAL_QA===true,source_sha:SOURCE_SHA,version:'0.2.0-studio',python_execution:'SKIP',sdk:'UNKNOWN'});
  if(request.method==='POST'){
   if(request.headers.get('origin')!==url.origin)throw Object.assign(Error('동일한 사이트에서만 요청할 수 있습니다.'),{status:403});
   if(!(request.headers.get('content-type')||'').startsWith('application/json'))throw Error('JSON 형식으로 입력해 주세요.');
  }
  if(path==='/api/rpc'&&request.method==='POST'){
   // Browser UI invokes the same three actual MCP handlers and response contract.
   const body=await readBounded(request);const r=await core.fetch(new Request(url.origin+'/mcp',{method:'POST',headers:{'content-type':'application/json'},body}));return r;
  }
  if(path==='/api/draft'&&request.method==='POST'){
   const args=JSON.parse(await readBounded(request));if(!args||typeof args!=='object'||Array.isArray(args))throw Error('입력은 JSON 객체여야 합니다.');if(Object.keys(args).some(k=>!['project_name','description','spec_json'].includes(k)))throw Error('허용되지 않은 입력입니다.');const p=await generate(args);return json({...p,saved:false});
  }
  if(path==='/api/projects'){
   if(request.method==='GET')return json(await listProjects(request,env));
   if(request.method==='POST'){requireWrite(request,env);return json(await createProject(request,env,JSON.parse(await readBounded(request))),201);}
   return json({error:'지원하지 않는 요청 방식입니다.'},405);
  }
  const m=path.match(/^\/api\/projects\/([a-f0-9-]+)(?:\/(tools|test|package))?$/);if(!m)return json({error:'Not found'},404);
  if(request.method==='POST'&&m[2]==='tools')return json(await addTool(request,env,m[1],JSON.parse(await readBounded(request))),201);
  if(request.method!=='GET')return json({error:'지원하지 않는 요청 방식입니다.'},405);
  const p=await getProject(request,env,m[1]);if(!m[2])return json(p);if(m[2]==='test')return json(await verifyProject(p));
  if(m[2]==='package'){const pkg=await packageProject(p);return new Response(pkg.bytes,{headers:{...secure,'content-type':'application/zip','content-disposition':`attachment; filename="${p.project_name}-${p.id.slice(0,8)}.zip"`,'x-content-sha256':pkg.sha256}});}
  return json({error:'Not found'},404);
 }catch(e){return json({error:e instanceof SyntaxError?'JSON 형식이 올바르지 않습니다. 괄호·따옴표를 확인해 주세요.':e.message},e.status||400);}
 }
};
},contract_json:{type:'string',minLength:2,maxLength:120000}},required:['project_name','contract_json'],additionalProperties:false}},
];
function validateExtra(tool,args){if(!args||typeof args!=='object'||Array.isArray(args)||Object.keys(args).some(k=>!Object.hasOwn(tool.inputSchema.properties,k))||tool.inputSchema.required.some(k=>typeof args[k]!=='string'))throw Error('필수 입력 또는 입력 형식을 확인해 주세요.');}
const secure={'cache-control':'no-store','x-content-type-options':'nosniff','referrer-policy':'same-origin'};
const textResponse=(s,type)=>new Response(s,{headers:{...secure,'content-type':type}});
export default {
 async fetch(request,env={}){
 const url=new URL(request.url),path=url.pathname;
 if(path==='/studio.js'&&request.method==='GET')return textResponse(CLIENT,'text/javascript; charset=utf-8');
 if(path==='/studio.css'&&request.method==='GET')return textResponse(CSS,'text/css; charset=utf-8');
 if(path==='/'&&request.method==='GET')return new Response(PAGE,{headers:{...secure,'content-type':'text/html; charset=utf-8','content-security-policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'self' https://chatgpt.com"}});
 if(path==='/mcp'){
  // Log only presence, never identity, prompts, specs, tokens or generated files.
  console.log(JSON.stringify({event:'forge-identity-boundary',authenticated:!!request.headers.get('oai-authenticated-user-id'),writes_enabled:writable(env)}));
  if(request.method!=='POST'||!writable(env))return core.fetch(request);
  let msg;try{msg=JSON.parse(await readBounded(request.clone()));}catch{return core.fetch(request);}
  if(msg?.jsonrpc!=='2.0'||!Object.hasOwn(msg,'id')||!['tools/list','tools/call'].includes(msg.method))return core.fetch(request);
  const base=await core.fetch(request.clone());if(base.status!==200)return base;const standard=await base.clone().json();if(standard.error&&msg.method!=='tools/call')return base;
  if(msg.method==='tools/list'){if(!standard.result)return base;standard.result.tools.push(...extraTools.map(t=>({...t,annotations:{readOnlyHint:['forge_test','forge_package'].includes(t.name),destructiveHint:false,openWorldHint:false}})));return json(standard);}
  const tool=extraTools.find(t=>t.name===msg.params?.name);if(!tool)return base;
  try{subject(request);validateExtra(tool,msg.params.arguments);const a=msg.params.arguments;let output;
   if(tool.name==='forge_create'||tool.name==='forge_import_openapi')output=await createProject(request,env,a);
   if(tool.name==='forge_add_tool')output=await addTool(request,env,a.project_id,{template:a.template});
   if(tool.name==='forge_test')output=await verifyProject(await getProject(request,env,a.project_id));
   if(tool.name==='forge_package'){const p=await getProject(request,env,a.project_id),pkg=await packageProject(p);output={project_id:p.id,sha256:pkg.sha256,bytes:pkg.bytes.length,download_path:'/api/projects/'+p.id+'/package',python_execution:'SKIP'};}
   return json({jsonrpc:'2.0',id:msg.id,result:{content:[{type:'text',text:JSON.stringify(output)}],structuredContent:output,isError:false}});
  }catch(e){return json({jsonrpc:'2.0',id:msg.id,result:{isError:true,content:[{type:'text',text:e.message}]}});}
 }
 if(!path.startsWith('/api/'))return json({error:'Not found'},404);
 try{
  if(path==='/api/session'&&request.method==='GET')return json({authenticated:!!request.headers.get('oai-authenticated-user-id'),writes_enabled:writable(env)&&!!request.headers.get('oai-authenticated-user-id'),storage:env.BUCKET?'R2':'unavailable',local_qa:env.LOCAL_QA===true,source_sha:SOURCE_SHA,version:'0.2.0-studio',python_execution:'SKIP',sdk:'UNKNOWN'});
  if(request.method==='POST'){
   if(request.headers.get('origin')!==url.origin)throw Object.assign(Error('동일한 사이트에서만 요청할 수 있습니다.'),{status:403});
   if(!(request.headers.get('content-type')||'').startsWith('application/json'))throw Error('JSON 형식으로 입력해 주세요.');
  }
  if(path==='/api/rpc'&&request.method==='POST'){
   // Browser UI invokes the same three actual MCP handlers and response contract.
   const body=await readBounded(request);const r=await core.fetch(new Request(url.origin+'/mcp',{method:'POST',headers:{'content-type':'application/json'},body}));return r;
  }
  if(path==='/api/draft'&&request.method==='POST'){
   const args=JSON.parse(await readBounded(request));if(!args||typeof args!=='object'||Array.isArray(args))throw Error('입력은 JSON 객체여야 합니다.');if(Object.keys(args).some(k=>!['project_name','description','spec_json'].includes(k)))throw Error('허용되지 않은 입력입니다.');const p=await generate(args);return json({...p,saved:false});
  }
  if(path==='/api/projects'){
   if(request.method==='GET')return json(await listProjects(request,env));
   if(request.method==='POST'){requireWrite(request,env);return json(await createProject(request,env,JSON.parse(await readBounded(request))),201);}
   return json({error:'지원하지 않는 요청 방식입니다.'},405);
  }
  const m=path.match(/^\/api\/projects\/([a-f0-9-]+)(?:\/(tools|test|package))?$/);if(!m)return json({error:'Not found'},404);
  if(request.method==='POST'&&m[2]==='tools')return json(await addTool(request,env,m[1],JSON.parse(await readBounded(request))),201);
  if(request.method!=='GET')return json({error:'지원하지 않는 요청 방식입니다.'},405);
  const p=await getProject(request,env,m[1]);if(!m[2])return json(p);if(m[2]==='test')return json(await verifyProject(p));
  if(m[2]==='package'){const pkg=await packageProject(p);return new Response(pkg.bytes,{headers:{...secure,'content-type':'application/zip','content-disposition':`attachment; filename="${p.project_name}-${p.id.slice(0,8)}.zip"`,'x-content-sha256':pkg.sha256}});}
  return json({error:'Not found'},404);
 }catch(e){return json({error:e instanceof SyntaxError?'JSON 형식이 올바르지 않습니다. 괄호·따옴표를 확인해 주세요.':e.message},e.status||400);}
 }
};
