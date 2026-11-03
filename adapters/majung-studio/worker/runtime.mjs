const baseHeaders={'cache-control':'no-store','x-content-type-options':'nosniff','referrer-policy':'same-origin'};
const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{...baseHeaders,'content-type':'application/json; charset=utf-8'}});
const MAX_BODY=524288;
async function body(req){
 if(!req.headers.get('content-type')?.includes('application/json'))throw Error('JSON 입력이 필요합니다.');
 const reader=req.body?.getReader();if(!reader)throw Error('입력이 없습니다.');
 let count=0, chunks=[];
 while(true){const {done,value}=await reader.read();if(done)break;count+=value.length;if(count>MAX_BODY){await reader.cancel();throw Error('입력이 512KiB를 초과합니다.');}chunks.push(value);}
 const bytes=new Uint8Array(count);let off=0;for(const c of chunks){bytes.set(c,off);off+=c.length;}
 return JSON.parse(new TextDecoder().decode(bytes));
}
function backend(env){
 if(!env.MCP_BACKEND_URL||!env.MCP_BACKEND_TOKEN)return null;
 const u=new URL(env.MCP_BACKEND_URL);
 const exact=env.MCP_BACKEND_ALLOWED_HOST;
 if(exact!==undefined&&exact!==null&&(!/^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/.test(exact)||exact.includes('..')))throw Error('유효하지 않은 서버 허용 호스트입니다.');
 const permitted=exact?u.hostname===exact:u.hostname.endsWith('.up.railway.app');
 if(u.protocol!=='https:'||!permitted||u.username||u.password||u.port||u.pathname!=='/mcp'||u.search||u.hash)throw Error('허용된 MCP 백엔드 주소가 아닙니다.');
 return u.toString();
}
const MCP_PROTOCOL='2026-07-28';
const MCP_CLIENT_INFO={name:'ALDOL MAJUNG Studio',version:'1.0.0'};
function mirrorName(name){
 if(typeof name!=='string'||!name)throw Error('MCP 도구 이름이 필요합니다.');
 if(/^[\x21-\x7e]+$/.test(name))return name;
 // Names with non-ASCII characters use the MCP mirrored-header sentinel.
 const bytes=new TextEncoder().encode(name);
 let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);
 return '=?base64?'+btoa(binary)+'?=';
}
async function rpc(url,secret,method,params={},asset=false){
 // The Asset Factory proxy is a separate, legacy Sites transport; preserve
 // it exactly until a separately approved migration.
 const modern=!asset;
 const mcpParams=modern?{...params,_meta:{
   ...(params._meta??{}),
   'io.modelcontextprotocol/protocolVersion':MCP_PROTOCOL,
   'io.modelcontextprotocol/clientCapabilities':{},
   'io.modelcontextprotocol/clientInfo':MCP_CLIENT_INFO
 }}:params;
 const headers={'content-type':'application/json','accept':'application/json, text/event-stream',
   ...(asset?{'OAI-Sites-Authorization':'Bearer '+secret}:{'Authorization':'Bearer '+secret})};
 if(modern){
   headers['MCP-Protocol-Version']=MCP_PROTOCOL;
   headers['Mcp-Method']=method;
   if(method==='tools/call')headers['Mcp-Name']=mirrorName(params.name);
 }
 const r=await fetch(url,{method:'POST',redirect:'error',headers,
   body:JSON.stringify({jsonrpc:'2.0',id:crypto.randomUUID(),method,params:mcpParams}),
   signal:AbortSignal.timeout(60000)});
 if(!r.ok)throw Error(asset?'Asset Factory 연결을 확인할 수 없습니다. (HTTP '+r.status+')':'전문 서버 응답 오류 (HTTP '+r.status+')');
 // Read responses with a byte-bound instead of trusting Content-Length.
 const reader=r.body?.getReader();if(!reader)throw Error('전문 서버 응답이 없습니다.');
 let size=0;const chunks=[];while(true){
  const {done,value}=await reader.read();if(done)break;
  size+=value.length;if(size>2097152){await reader.cancel();throw Error('응답 크기 제한을 초과했습니다.');}
  chunks.push(value);
 }
 const bytes=new Uint8Array(size);let at=0;for(const chunk of chunks){bytes.set(chunk,at);at+=chunk.length;}
 let d;try{d=JSON.parse(new TextDecoder().decode(bytes))}catch{throw Error('지원되지 않는 MCP 응답 형식입니다.');}
 if(d?.jsonrpc!=='2.0'||d.error||!d.result)throw Error('MCP 요청이 거부되었습니다.');
 if(modern&&d.result.resultType!=='complete')throw Error('최신 MCP 응답 계약이 일치하지 않습니다.');
 if(d.result.isError)throw Error('전문 도구가 입력 또는 실행을 거부했습니다.');
 return d.result;
}
function unwrap(r){let value=r.structuredContent;if(value?.result)value=value.result;if(value!==undefined)return value;const t=r.content?.find(x=>x.type==='text')?.text;if(t){try{return JSON.parse(t)}catch{return {text:t}}}throw Error('도구 결과가 없습니다.');}
async function runTool(name,args,env){
 const tool=TOOLS.find(t=>t.name===name);if(!tool)throw Error('이 회사에서 제공하지 않는 도구입니다.');
 if(!args||typeof args!=='object'||Array.isArray(args)||Object.keys(args).some(k=>!Object.hasOwn(tool.inputSchema.properties,k))||tool.inputSchema.required.some(k=>typeof args[k]!=='string'))throw Error('도구 입력 필드를 확인하세요.');
 for(const v of Object.values(args))if(v!==null&&(typeof v!=='string'||v.length>262144))throw Error('문자열 입력 크기를 확인하세요.');
 const url=backend(env);if(!url)throw Error('전문 서버 연결 대기: Cloudflare 백엔드 이전 진행 중');
 return unwrap(await rpc(url,env.MCP_BACKEND_TOKEN,'tools/call',{name,arguments:args}));
}
export default {async fetch(req,env){
 const u=new URL(req.url), path=u.pathname;
 if(req.method==='GET'&&['/','/client.js','/style.css'].includes(path))return new Response(path==='/'?PAGE:path==='/client.js'?CLIENT:CSS,{headers:{...baseHeaders,'content-type':path==='/'?'text/html; charset=utf-8':path==='/client.js'?'application/javascript; charset=utf-8':'text/css; charset=utf-8','content-security-policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'self' https://chatgpt.com"}});
 if(path==='/api/status'&&req.method==='GET'){
  try{const url=backend(env);if(!url)return json({company:COMPANY,connected:false,status:'BLOCKED',reason:'Cloudflare 백엔드 이전 진행 중: 전문 서버 미연결',sdk:'2.0.0',asset_factory:COMPANY==='bonsae'?'metadata_only; authentication needs verification':null,checked_at:new Date().toISOString()});
   await rpc(url,env.MCP_BACKEND_TOKEN,'tools/list');return json({company:COMPANY,connected:true,status:'CONNECTED',checked_at:new Date().toISOString()});
  }catch{return json({company:COMPANY,connected:false,status:'ERROR',reason:'전문 서버 연결을 확인할 수 없습니다.',checked_at:new Date().toISOString()},502);}
 }
 if(!['/mcp','/api/call','/api/assets'].includes(path))return json({error:'Not found'},404);
 if(req.method!=='POST')return json({error:'POST required'},405);
 if(path.startsWith('/api/')&&req.headers.get('origin')!==u.origin)return json({error:'Origin rejected'},403);
 let b;try{b=await body(req)}catch(e){return json({error:e.message},400);}
 if(path==='/api/call'){
  try{return json({result:await runTool(b.name,b.arguments,env),checked_at:new Date().toISOString()})}catch(e){return json({error:e.message},backend(env)?422:503);}
 }
 if(path==='/api/assets'){
  if(COMPANY!=='bonsae')return json({error:'Not found'},404);
  if(!env.ASSET_FACTORY_TOKEN)return json({error:'Asset Factory 인증 연동 대기. 파일 검사는 수행되지 않았습니다.'},503);
  try{const result=await rpc('https://aldol-asset-factory-studio.al-dori.chatgpt.site/mcp',env.ASSET_FACTORY_TOKEN,'tools/call',{name:'audit_preview',arguments:b.manifest},true);return json({result:unwrap(result),scope:'caller_metadata_only',checked_at:new Date().toISOString()});}catch(e){return json({error:e.message},502);}
 }
 const id=b?.id??null, out=result=>json({jsonrpc:'2.0',id,result});
 if(b?.jsonrpc!=='2.0'||typeof b.method!=='string')return json({jsonrpc:'2.0',id:null,error:{code:-32600,message:'Invalid request'}},400);
 if(b.method==='notifications/initialized')return new Response(null,{status:202});
 if(b.method==='server/discover')return out({supportedVersions:['2026-07-28'],capabilities:{tools:{}}});
 if(b.method==='initialize')return out({protocolVersion:'2026-07-28',capabilities:{tools:{}},serverInfo:{name:'ALDOL '+COMPANY.toUpperCase()+' Studio',version:'1.0.0'}});
 if(b.method==='tools/list')return out({tools:TOOLS});
 if(b.method==='tools/call'){
  try{const value=await runTool(b.params?.name,b.params?.arguments??{},env);return out({content:[{type:'text',text:JSON.stringify(value)}],structuredContent:value,isError:false});}
  catch(e){return out({content:[{type:'text',text:e.message}],isError:true});}
 }
 return json({jsonrpc:'2.0',id,error:{code:-32601,message:'Method not found'}});
}};
