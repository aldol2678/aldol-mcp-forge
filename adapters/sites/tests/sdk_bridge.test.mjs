import test from "node:test";
import assert from "node:assert/strict";
import worker from "../worker/index.js";
import {sdkReady, createSdkJob, readSdkJob} from "../worker/sdk-bridge.js";

const secret="sdk-job-test-secret-"+("x".repeat(48));
const origin="https://forge.test";
const makeReq=(url,body,user="alice")=>new Request(origin+url,{
  method:body===undefined?"GET":"POST",
  headers:{
    "content-type":"application/json",
    "origin":origin,
    ...(user?{"oai-authenticated-user-id":user}:{}),
  },
  ...(body===undefined?{}:{body:JSON.stringify(body)}),
});
class Bucket{
 data=new Map();
 async get(key){const value=this.data.get(key);return value?{json:async()=>JSON.parse(value)}:null;}
 async put(key,value,opt){if(opt?.onlyIf?.etagDoesNotMatch==="*"&&this.data.has(key))return null;this.data.set(key,value);return {etag:key};}
 async list({prefix}){return {objects:[...this.data.keys()].filter(key=>key.startsWith(prefix)).map(key=>({key})),truncated:false};}
}
const base=()=>({FORGE_WRITES_VERIFIED:"1",BUCKET:new Bucket()});
const ready=()=>({...base(),SDK_BRIDGE_ENABLED:"1",
  SDK_BRIDGE_URL:"https://verified.private.example/v1/sdk/jobs",
  SDK_BRIDGE_ORIGIN:"https://verified.private.example",
  SDK_BRIDGE_SECRET:secret});

test("SDK service is disabled unless all private host settings exist",async()=>{
 const e=base();
 assert.equal(sdkReady(e),false);
 assert.equal((await (await worker.fetch(makeReq("/api/session"),e)).json()).sdk_verifier_available,false);
 const p=await (await worker.fetch(makeReq("/api/projects",{project_name:"sdk-disabled",description:"HTML 게임 검사"}),e)).json();
 const response=await worker.fetch(makeReq("/api/projects/"+p.id+"/sdk",{}),e);
 assert.equal(response.status,503);
 const old=await (await worker.fetch(makeReq("/api/projects/"+p.id+"/test"),e)).json();
 assert.equal(old.official_sdk.status,"SKIP");
 for(const cfg of [
   {...ready(),SDK_BRIDGE_URL:"http://verified.private.example/v1/sdk/jobs"},
   {...ready(),SDK_BRIDGE_ORIGIN:"https://other.example"},
   {...ready(),SDK_BRIDGE_SECRET:"weak"},
 ])assert.equal(sdkReady(cfg),false);
});

test("actual stored project ZIP is signed and posted; results are owner scoped",async()=>{
 const e=ready(),p=await (await worker.fetch(makeReq("/api/projects",
  {project_name:"sdk-real-project",description:"HTML 게임 검사"}),e)).json();
 let expectedHash;
 const submit=async (url,opts)=>{
   assert.equal(url,e.SDK_BRIDGE_URL);
   assert.equal(opts.redirect,"manual");
   assert.equal(opts.method,"POST");
   assert.ok(opts.headers["X-Forge-Signature"]);
   const body=JSON.parse(opts.body);
   assert.deepEqual(Object.keys(body).sort(),["project_id","sha256","subject_hash","zip_base64"]);
   assert.equal(body.project_id,p.id);
   assert.match(body.subject_hash,/^[a-f0-9]{64}$/);
   assert.equal("owner_id" in body,false);
   assert.ok(body.zip_base64.startsWith("UEs"));
   expectedHash=body.sha256;
   return {status:202,redirected:false,json:async()=>({
     job_id:"a".repeat(64),project_id:p.id,sha256:expectedHash,status:"QUEUED",
   })};
 };
 const start=await createSdkJob(makeReq("/api/projects/"+p.id+"/sdk",{}),e,p.id,submit);
 assert.equal(start.status,"QUEUED");
 assert.equal(start.official_sdk,"QUEUED");
 assert.equal([...e.BUCKET.data.keys()].filter(k=>k.includes("sdk-job-latest")).length,1);
 const status=await readSdkJob(makeReq("/api/projects/"+p.id+"/sdk"),e,p.id,async(url,opts)=>{
   assert.equal(new URL(url).pathname,"/v1/sdk/jobs/status");
   const body=JSON.parse(opts.body);
   assert.equal(body.job_id,"a".repeat(64));
   return {status:200,redirected:false,json:async()=>({
     job_id:body.job_id,project_id:p.id,sha256:expectedHash,status:"PASS",
     verification:{passed:true,official_sdk:"PASS",inmemory:"PASS",stdio:"PASS",network_used:false,sdk_version:"2.0.0"},
   })};
 });
 assert.equal(status.official_sdk,"PASS");
 assert.equal(status.python_execution,"PASS");
 await assert.rejects(readSdkJob(makeReq("/api/projects/"+p.id+"/sdk",undefined,"bob"),e,p.id,async()=>{throw Error("must not fetch");}));
 const old=await (await worker.fetch(makeReq("/api/projects/"+p.id+"/test"),e)).json();
 assert.equal(old.official_sdk.status,"SKIP");
});

test("forged success and mismatched artifact hashes never count as PASS",async()=>{
 const e=ready(),p=await (await worker.fetch(makeReq("/api/projects",
  {project_name:"sdk-tamper-proof",description:"JSON 검사"}),e)).json();
 const req=makeReq("/api/projects/"+p.id+"/sdk",{});
 const job=await createSdkJob(req,e,p.id,async()=>({
   status:202,redirected:false,json:async()=>({
     job_id:"b".repeat(64),project_id:p.id,sha256:"a".repeat(64),status:"QUEUED",
   }),
 })).then(()=>null).catch(x=>x);
 assert.ok(job instanceof Error);
 // Mismatching signed backend response gets refused before persisted record.
 assert.equal([...e.BUCKET.data.keys()].some(k=>k.includes("sdk-job-latest")),false);
});

test("missing authenticated Sites user is rejected before SDK network request",async()=>{
 const e=ready();
 let touched=false;
 const req=makeReq("/api/projects/00000000-0000-0000-0000-000000000000/sdk",{},null);
 await assert.rejects(createSdkJob(req,e,"00000000-0000-0000-0000-000000000000",async()=>{touched=true;}));
 assert.equal(touched,false);
});

test('job states retain TIMEOUT and UNKNOWN; incomplete SDK evidence cannot PASS',async()=>{
 const e=ready(),p=await (await worker.fetch(makeReq('/api/projects',{project_name:'sdk-states',description:'JSON 검사'}),e)).json();
 let sha;
 await createSdkJob(makeReq('/sdk',{}),e,p.id,async(url,opts)=>{
  sha=JSON.parse(opts.body).sha256;
  return {status:202,json:async()=>({job_id:'c'.repeat(64),project_id:p.id,sha256:sha,status:'QUEUED'})};
 });
 for(const [status,verification,expected] of [
  ['RUNNING',undefined,'RUNNING'],['QUEUED',undefined,'QUEUED'],
  ['TIMEOUT',undefined,'TIMEOUT'],['INTERRUPTED',undefined,'UNKNOWN'],
  ['REJECTED',undefined,'FAIL'],['PASS',{passed:true,official_sdk:'PASS'},'FAIL'],
  ['PASS',{passed:true,official_sdk:'PASS',inmemory:'PASS',stdio:'PASS',network_used:false,sdk_version:'1.0.0'},'FAIL'],
 ]){
  const r=await readSdkJob(makeReq('/sdk'),e,p.id,async()=>({status:200,json:async()=>({job_id:'c'.repeat(64),project_id:p.id,sha256:sha,status,verification})}));
  assert.equal(r.official_sdk,expected,status);
  if(status==='PASS')assert.equal(r.status,'FAIL');
 }
});
