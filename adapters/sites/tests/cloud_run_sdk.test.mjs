import test from "node:test";
import assert from "node:assert/strict";
import {createHash} from "node:crypto";
import worker from "../worker/index.js";
import {sdkReady, createSdkJob, readSdkJob} from "../worker/sdk-bridge.js";

const origin="https://forge.test";
const secret="cloudrun-test-hmac-secret-"+("x".repeat(48));
class Bucket {
  data=new Map();
  async get(key){const v=this.data.get(key);return v?{json:async()=>JSON.parse(v)}:null;}
  async put(k,v,options){if(options?.onlyIf?.etagDoesNotMatch==="*"&&this.data.has(k))return null;this.data.set(k,v);return {etag:k};}
  async list({prefix}){return {objects:[...this.data.keys()].filter(k=>k.startsWith(prefix)).map(key=>({key})),truncated:false};}
}
const env=()=>({
  BUCKET:new Bucket(),FORGE_WRITES_VERIFIED:"1",
  SDK_BRIDGE_ENABLED:"1",SDK_BRIDGE_MODE:"cloudrun-sync",
  SDK_BRIDGE_URL:"https://forge-verifier.example/v1/sdk/jobs",
  SDK_BRIDGE_ORIGIN:"https://forge-verifier.example",
  SDK_BRIDGE_SECRET:secret,
});
const request=(path,body,user="alice")=>new Request(origin+path,{
  method:body===undefined?"GET":"POST",
  headers:{"content-type":"application/json",origin,...(user?{"oai-authenticated-user-id":user}:{})},
  ...(body===undefined?{}:{body:JSON.stringify(body)}),
});
const hex=s=>createHash("sha256").update(s).digest("hex");

test("Cloud Run mode requires explicit server-side opt-in and valid HTTPS",()=>{
  const e=env();
  assert.equal(sdkReady(e),true);
  for(const changed of [
    {...e,SDK_BRIDGE_ENABLED:"0"},
    {...e,SDK_BRIDGE_MODE:"unknown"},
    {...e,SDK_BRIDGE_URL:"http://forge-verifier.example/v1/sdk/jobs"},
    {...e,SDK_BRIDGE_SECRET:"short"},
  ])assert.equal(sdkReady(changed),false);
});

test("real Studio ZIP yields verified PASS with durable Site R2 readback, no Python status call",async()=>{
  const e=env();
  const created=await (await worker.fetch(request("/api/projects",
    {project_name:"cloudrun-verify",description:"HTML 게임 검사"}),e)).json();
  const pid=created.id;
  let sent=0;
  const executor=async(url,req)=>{
    sent++;
    assert.equal(url,e.SDK_BRIDGE_URL);
    assert.ok(req.headers["X-Forge-Signature"]);
    const args=JSON.parse(req.body);
    const job_id=hex(args.subject_hash+":"+args.project_id+":"+args.sha256);
    return {status:200,redirected:false,json:async()=>({
      job_id,project_id:pid,sha256:args.sha256,status:"PASS",
      verification:{passed:true,official_sdk:"PASS",sdk_version:"2.0.0",
        inmemory:"PASS",stdio:"PASS",network_used:false},
    })};
  };
  const started=await createSdkJob(request("/api/projects/"+pid+"/sdk",{}),e,pid,executor);
  assert.equal(started.official_sdk,"PASS");
  assert.equal(started.python_execution,"PASS");
  const afterReload=await readSdkJob(request("/api/projects/"+pid+"/sdk"),e,pid,async()=>{
    throw Error("Cloud Run status endpoint must not be needed for synchronous results");
  });
  assert.equal(afterReload.official_sdk,"PASS");
  assert.equal(afterReload.available,true);
  assert.equal(sent,1);
  await assert.rejects(readSdkJob(request("/api/projects/"+pid+"/sdk",undefined,"bob"),e,pid));
});

test("Cloud Run mismatch, incomplete evidence and empty job never create false PASS",async()=>{
  const e=env();
  const created=await (await worker.fetch(request("/api/projects",
    {project_name:"cloudrun-no-fake-pass",description:"JSON 검사"}),e)).json();
  const pid=created.id;
  const forged=async(url,req)=>{
    const args=JSON.parse(req.body);
    return {status:200,redirected:false,json:async()=>({
      job_id:"a".repeat(64),project_id:pid,sha256:args.sha256,status:"PASS",
      verification:{passed:true,official_sdk:"PASS",sdk_version:"2.0.0",
        inmemory:"PASS",stdio:"PASS",network_used:false},
    })};
  };
  await assert.rejects(createSdkJob(request("/api/projects/"+pid+"/sdk",{}),e,pid,forged));
  assert.equal([...e.BUCKET.data.keys()].filter(k=>k.includes("sdk-job-latest")).length,0);
  const incomplete=async(url,req)=>{
    const args=JSON.parse(req.body);
    return {status:200,redirected:false,json:async()=>({
      job_id:hex(args.subject_hash+":"+args.project_id+":"+args.sha256),
      project_id:pid,sha256:args.sha256,status:"PASS",
      verification:{passed:true,official_sdk:"PASS",sdk_version:"1.0.0"},
    })};
  };
  const value=await createSdkJob(request("/api/projects/"+pid+"/sdk",{}),e,pid,incomplete);
  assert.equal(value.official_sdk,"FAIL");
  const restored=await readSdkJob(request("/api/projects/"+pid+"/sdk"),e,pid);
  assert.equal(restored.official_sdk,"FAIL");
});
