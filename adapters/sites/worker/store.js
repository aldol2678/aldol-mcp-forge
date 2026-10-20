import { generate, digest, verifyProject, zipFiles } from './generator.js';
const errors=(message,status=400)=>Object.assign(new Error(message),{status});
export const writable=env=>env?.FORGE_WRITES_VERIFIED==='1'&&!!env?.BUCKET;
export function subject(request){const id=request.headers.get('oai-authenticated-user-id');if(!id||id.length>512)throw errors('ChatGPT 로그인과 사용자 식별이 필요합니다.',403);return id;}
async function prefix(request){return 'studio/v1/'+await digest(subject(request))+'/';}
const idCheck=id=>{if(typeof id!=='string'||!/^[a-f0-9-]{36}$/.test(id))throw errors('프로젝트를 찾을 수 없습니다.',404);return id;};
export async function listProjects(request,env){const pre=await prefix(request);if(!env?.BUCKET)return {projects:[],storage:'unavailable'};const result=await env.BUCKET.list({prefix:pre+'projects/',limit:100});const projects=[];for(const o of result.objects){const item=await env.BUCKET.get(o.key);if(item){const p=await item.json();const {files,spec_json,contract_json,...summary}=p;projects.push(summary);}}return {projects:projects.sort((a,b)=>b.created_at.localeCompare(a.created_at)),truncated:result.truncated};}
export async function getProject(request,env,id){const pre=await prefix(request);idCheck(id);if(!env?.BUCKET)throw errors('저장소가 아직 연결되지 않았습니다.',503);const found=await env.BUCKET.get(pre+'projects/'+id+'.json');if(!found)throw errors('프로젝트를 찾을 수 없습니다.',404);return found.json();}
export function requireWrite(request,env){subject(request);if(!writable(env))throw errors('인증 연결 검증 전에는 생성·편집 기능을 사용할 수 없습니다.',403);}
function exact(args,keys,required){if(!args||typeof args!=='object'||Array.isArray(args))throw errors('입력은 JSON 객체여야 합니다.');if(Object.keys(args).some(k=>!keys.includes(k)))throw errors('허용되지 않은 입력 항목이 있습니다.');if(required.some(k=>!Object.hasOwn(args,k)))throw errors('필수 입력 항목이 누락되었습니다.');}
export async function createProject(request,env,args){
 requireWrite(request,env);exact(args,['project_name','description','spec_json','contract_json'],['project_name']);if(['description','spec_json','contract_json'].filter(k=>Object.hasOwn(args,k)).length!==1)throw errors('설명·OpenAPI·도구 계약 JSON 중 하나만 입력해 주세요.');
 const p=await generate(args),pre=await prefix(request);const count=await env.BUCKET.list({prefix:pre+'projects/',limit:100});if(count.truncated||count.objects.length>=100)throw errors('작업공간은 최대 100개 버전까지 보관합니다.',409);
 p.id=crypto.randomUUID();p.parent_id=null;
 // Conditional name reservation rejects duplicates atomically; the receipt is
 // authoritative and readable if a later object write fails. No automatic retry.
 const reservation={id:p.id,project_name:p.project_name,status:'reserved'};
 const taken=await env.BUCKET.put(pre+'names/'+p.project_name+'.json',JSON.stringify(reservation),{onlyIf:{etagDoesNotMatch:'*'}});
 if(!taken)throw errors('이미 존재하거나 생성이 시작된 이름입니다. 다른 프로젝트 이름을 사용해 주세요.',409);
 const saved=await env.BUCKET.put(pre+'projects/'+p.id+'.json',JSON.stringify(p),{onlyIf:{etagDoesNotMatch:'*'}});if(!saved)throw errors('저장 충돌이 발생했습니다. 프로젝트 목록을 확인해 주세요.',409);
 return p;
}
export async function addTool(request,env,id,args){
 requireWrite(request,env);exact(args,['template'],['template']);const p=await getProject(request,env,id);if(p.kind!=='curated')throw errors('이 프로젝트 유형은 도구 편집을 지원하지 않습니다. 새 프로젝트를 생성해 주세요.');if(p.tools.includes(args.template))throw errors('이미 추가된 도구입니다.');
 const pre=await prefix(request),count=await env.BUCKET.list({prefix:pre+'projects/',limit:100});if(count.truncated||count.objects.length>=100)throw errors('최대 100개 버전까지 보관합니다.',409);
 const next=await generate({project_name:p.project_name,description:p.description},[...p.tools,args.template],{version:p.version,hash:await digest(p.files['manifest.json'])});next.id=crypto.randomUUID();next.parent_id=p.id;
 if(!await env.BUCKET.put(pre+'projects/'+next.id+'.json',JSON.stringify(next),{onlyIf:{etagDoesNotMatch:'*'}}))throw errors('저장 충돌이 발생했습니다.',409);return next;
}
export async function packageProject(p){const integrity=await verifyProject(p);if(integrity.integrity.status!=='PASS')throw errors('파일 무결성 검사에 실패했습니다. ZIP 생성을 중단합니다.',409);const files={...p.files};files['mcp-config.json']=JSON.stringify({mcpServers:{[p.project_name]:{command:'python3',args:['/ABSOLUTE/PATH/'+p.project_name+'/server.py']}}},null,2)+'\n';files['studio-validation.json']=JSON.stringify({source_sha:p.source_sha,...integrity},null,2)+'\n';const hashes={};for(const[n,v]of Object.entries(files))hashes[n]=await digest(v);files['SHA256SUMS']=Object.entries(hashes).map(([n,h])=>h+'  '+n).join('\n')+'\n';const bytes=zipFiles(files);return {bytes,sha256:await digest(bytes)};}
