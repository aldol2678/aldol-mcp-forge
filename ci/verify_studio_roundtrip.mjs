// Real Worker signing -> local Python HTTP gateway -> SDK -> Worker readback.
// Synthetic identity and memory R2 only. Never production authentication/R2 evidence.
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {randomBytes} from 'node:crypto';
import assert from 'node:assert/strict';
import {createInterface} from 'node:readline';
import worker from '../adapters/sites/worker/index.js';
import {createSdkJob,readSdkJob} from '../adapters/sites/worker/sdk-bridge.js';
const root=await mkdtemp(join(tmpdir(),'forge-roundtrip-'));
const secret=randomBytes(48).toString('hex');
const python=process.env.FORGE_TEST_PYTHON||'python3';
const server=spawn(python,['-u','-c',`import os
from http.server import ThreadingHTTPServer
from bridge.sdk_job_gateway import JobStore,make_handler
s=ThreadingHTTPServer(('127.0.0.1',0),make_handler(JobStore(os.environ['FORGE_SDK_WORKSPACE_ROOT'],os.environ['FORGE_SDK_BRIDGE_SECRET'])))
print(s.server_port,flush=True)
s.serve_forever()`],{env:{...process.env,FORGE_SDK_WORKSPACE_ROOT:root,FORGE_SDK_BRIDGE_SECRET:secret},stdio:['ignore','pipe','pipe']});
try{
 const port=await new Promise((resolve,reject)=>{
  const lines=createInterface({input:server.stdout});
  const timer=setTimeout(()=>reject(Error('Gateway startup timeout')),10000);
  lines.once('line',line=>{clearTimeout(timer);resolve(Number(line));});
  server.once('exit',()=>{clearTimeout(timer);reject(Error('Gateway exited'));});
 });
 const data=new Map();
 const env={FORGE_WRITES_VERIFIED:'1',SDK_BRIDGE_ENABLED:'1',SDK_BRIDGE_URL:'https://test-only.invalid/v1/sdk/jobs',SDK_BRIDGE_ORIGIN:'https://test-only.invalid',SDK_BRIDGE_SECRET:secret,
 BUCKET:{async get(k){return data.has(k)?{json:async()=>JSON.parse(data.get(k))}:null;},async put(k,v,o){if(o?.onlyIf?.etagDoesNotMatch==='*'&&data.has(k))return null;data.set(k,v);return {etag:k};},async list({prefix}){return {objects:[...data.keys()].filter(k=>k.startsWith(prefix)).map(key=>({key})),truncated:false};}}};
 const req=(path,body,user='local-roundtrip')=>new Request('https://studio.test'+path,{method:body===undefined?'GET':'POST',headers:{'oai-authenticated-user-id':user,origin:'https://studio.test','content-type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});
 const fetcher=(url,options)=>fetch('http://127.0.0.1:'+port+new URL(url).pathname,options);
 const project=await (await worker.fetch(req('/api/projects',{project_name:'real-sdk-roundtrip',description:'HTML 게임 검사'}),env)).json();
 assert.ok(project.id);
 const created=await createSdkJob(req('/sdk',{}),env,project.id,fetcher);
 assert.equal(created.status,'QUEUED');
 const duplicate=await createSdkJob(req('/sdk',{}),env,project.id,fetcher);
 assert.equal(duplicate.job_id,created.job_id);
 let result;
 for(let n=0;n<120;n++){
  result=await readSdkJob(req('/sdk'),env,project.id,fetcher);
  if(!['QUEUED','RUNNING'].includes(result.status))break;
  await new Promise(resolve=>setTimeout(resolve,100));
 }
 assert.equal(result.official_sdk,'PASS',JSON.stringify(result));
 assert.equal(result.verification.sdk_version,'2.0.0');
 const refreshed=await readSdkJob(req('/sdk'),env,project.id,fetcher);
 assert.equal(refreshed.job_id,created.job_id);
 assert.equal(refreshed.official_sdk,'PASS');
 await assert.rejects(readSdkJob(req('/sdk',undefined,'other-user'),env,project.id,fetcher));
 console.log(JSON.stringify({scope:'local actual Worker HMAC + HTTP + Python SDK; synthetic identity and memory R2',project_id:project.id,duplicate_job_id:duplicate.job_id,refresh_persisted:true,...result},null,2));
}finally{
 server.kill('SIGTERM');
 await new Promise(resolve=>{if(server.exitCode!==null)resolve();else server.once('exit',resolve);});
 await rm(root,{recursive:true,force:true});
}
