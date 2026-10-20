import test from "node:test";
import assert from "node:assert/strict";
import {createHash, generateKeyPairSync, verify as rsaVerify} from "node:crypto";
import worker from "../worker/index.js";
import {sdkReady, createSdkJob, readSdkJob} from "../worker/sdk-bridge.js";

const keys=generateKeyPairSync("rsa",{modulusLength:2048});
const credentials=JSON.stringify({type:"service_account",project_id:"aram-slack-bridge-2026",
 client_email:"forge-sites-invoker@aram-slack-bridge-2026.iam.gserviceaccount.com",
 private_key:keys.privateKey.export({type:"pkcs8",format:"pem"})});
const verifierOrigin="https://forge-sdk-verifier-test.a.run.app";
const authorized=base=>({...base,SDK_BRIDGE_AUTH_MODE:"google-service-account",
 SDK_BRIDGE_GOOGLE_CREDENTIALS:credentials});
const googleToken=(e)=>["header",Buffer.from(JSON.stringify({iss:"https://accounts.google.com",
 aud:e.SDK_BRIDGE_ORIGIN,email:JSON.parse(credentials).client_email,
 exp:Math.floor(Date.now()/1000)+3600})).toString("base64url"),"signature"].join(".");
function withGoogle(e, executor){return async(url,req)=>{
 if(url==="https://oauth2.googleapis.com/token"){
  const assertion=new URLSearchParams(req.body).get("assertion");
  const parts=assertion.split(".");
  assert.equal(rsaVerify("RSA-SHA256",Buffer.from(parts[0]+"."+parts[1]),keys.publicKey,Buffer.from(parts[2],"base64url")),true);
  const claims=JSON.parse(Buffer.from(parts[1],"base64url"));
  assert.equal(claims.target_audience,e.SDK_BRIDGE_ORIGIN);
  assert.equal(claims.aud,"https://oauth2.googleapis.com/token");
  assert.equal(req.redirect,"manual");
  assert.equal(req.headers["X-Forge-Signature"],undefined);
  return new Response(JSON.stringify({id_token:googleToken(e)}),{status:200});
 }
 assert.equal(req.headers["Authorization"],"Bearer "+googleToken(e));
 return executor(url,req);
};}
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
  SDK_BRIDGE_URL:verifierOrigin+"/v1/sdk/jobs",
  SDK_BRIDGE_ORIGIN:verifierOrigin,
  SDK_BRIDGE_SECRET:secret,
});
const request=(path,body,user="alice")=>new Request(origin+path,{
  method:body===undefined?"GET":"POST",
  headers:{"content-type":"application/json",origin,...(user?{"oai-authenticated-user-id":user}:{})},
  ...(body===undefined?{}:{body:JSON.stringify(body)}),
});
const hex=s=>createHash("sha256").update(s).digest("hex");

test("Cloud Run mode requires explicit server-side opt-in and valid HTTPS",()=>{
  const e=authorized(env());
  assert.equal(sdkReady(e),true);
  for(const changed of [
    {...e,SDK_BRIDGE_ENABLED:"0"},
    {...e,SDK_BRIDGE_MODE:"unknown"},
    {...e,SDK_BRIDGE_URL:"http://forge-verifier.example/v1/sdk/jobs"},
    {...e,SDK_BRIDGE_SECRET:"short"},
  ])assert.equal(sdkReady(changed),false);
});

test("real Studio ZIP yields verified PASS with durable Site R2 readback, no Python status call",async()=>{
  const e=authorized(env());
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
  const started=await createSdkJob(request("/api/projects/"+pid+"/sdk",{}),e,pid,withGoogle(e,executor));
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
  const e=authorized(env());
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
  await assert.rejects(createSdkJob(request("/api/projects/"+pid+"/sdk",{}),e,pid,withGoogle(e,forged)));
  assert.equal([...e.BUCKET.data.keys()].filter(k=>k.includes("sdk-job-latest")).length,0);
  const incomplete=async(url,req)=>{
    const args=JSON.parse(req.body);
    return {status:200,redirected:false,json:async()=>({
      job_id:hex(args.subject_hash+":"+args.project_id+":"+args.sha256),
      project_id:pid,sha256:args.sha256,status:"PASS",
      verification:{passed:true,official_sdk:"PASS",sdk_version:"1.0.0"},
    })};
  };
  const value=await createSdkJob(request("/api/projects/"+pid+"/sdk",{}),e,pid,withGoogle(e,incomplete));
  assert.equal(value.official_sdk,"FAIL");
  const restored=await readSdkJob(request("/api/projects/"+pid+"/sdk"),e,pid);
  assert.equal(restored.official_sdk,"FAIL");
});

// A configured HMAC cannot make a private Google service invokable.
test("HMAC-only Cloud Run settings keep the execution button disabled",()=>{
 const e=env();
 assert.equal(sdkReady(e),false);
});

test("same immutable project result is reused without more billed verification",async()=>{
 const e=authorized(env());
 const p=await (await worker.fetch(request("/api/projects",{project_name:"cached-sdk",description:"HTML 검사"}),e)).json();
 let runs=0;
 const exec=withGoogle(e,async(url,req)=>{
  runs++; const a=JSON.parse(req.body);
  return new Response(JSON.stringify({job_id:hex(a.subject_hash+":"+a.project_id+":"+a.sha256),
   project_id:p.id,sha256:a.sha256,status:"PASS",verification:{passed:true,official_sdk:"PASS",
   inmemory:"PASS",stdio:"PASS",network_used:false,sdk_version:"2.0.0"}}));
 });
 await createSdkJob(request("/sdk",{}),e,p.id,exec);
 const again=await createSdkJob(request("/sdk",{}),e,p.id,async()=>{throw Error("no extra network");});
 assert.equal(again.status,"PASS");assert.equal(runs,1);
});

test("Cloud Run timeout is saved for refresh without becoming PASS",async()=>{
 const e=authorized(env());
 const p=await (await worker.fetch(request("/api/projects",{project_name:"timeout-sdk",description:"HTML 검사"}),e)).json();
 const r=await createSdkJob(request("/sdk",{}),e,p.id,withGoogle(e,async(url,req)=>{
  const a=JSON.parse(req.body);
  return new Response(JSON.stringify({job_id:hex(a.subject_hash+":"+a.project_id+":"+a.sha256),
   project_id:p.id,sha256:a.sha256,status:"TIMEOUT",verification:{passed:false,official_sdk:"TIMEOUT"}}));
 }));
 assert.equal(r.status,"TIMEOUT");
 assert.equal((await readSdkJob(request("/sdk"),e,p.id)).official_sdk,"TIMEOUT");
});

test("daily execution budget rejects further Cloud Run spending",async()=>{
 const e=authorized(env());
 const p=await (await worker.fetch(request("/api/projects",{project_name:"budget-sdk",description:"HTML 검사"}),e)).json();
 let runs=0;
 const exec=withGoogle(e,async(url,req)=>{
  runs++; const a=JSON.parse(req.body);
  return new Response(JSON.stringify({job_id:hex(a.subject_hash+":"+a.project_id+":"+a.sha256),
   project_id:p.id,sha256:a.sha256,status:"TIMEOUT",verification:{passed:false,official_sdk:"TIMEOUT"}}));
 });
 for(let i=0;i<30;i++) await createSdkJob(request("/sdk",{}),e,p.id,exec);
 await assert.rejects(createSdkJob(request("/sdk",{}),e,p.id,exec),e=>e.status===429);
 assert.equal(runs,30);
});

test("a Slack or other project identity cannot be reused as the Forge caller",()=>{
 const e=authorized(env());
 const c=JSON.parse(credentials);c.client_email="slack-bridge@aram-slack-bridge-2026.iam.gserviceaccount.com";
 assert.equal(sdkReady({...e,SDK_BRIDGE_GOOGLE_CREDENTIALS:JSON.stringify(c)}),false);
});

test("Google exchange failure never submits an HMAC job or persists false evidence",async()=>{
 const e=authorized(env());
 const p=await (await worker.fetch(request("/api/projects",{project_name:"iam-rejection",description:"HTML 검사"}),e)).json();
 let calls=0;
 await assert.rejects(createSdkJob(request("/sdk",{}),e,p.id,async(url)=>{
  calls++;assert.equal(url,"https://oauth2.googleapis.com/token");
  return new Response('{"error":"invalid_grant"}',{status:400});
 }),e=>e.status===502 && !e.message.includes("PRIVATE KEY"));
 assert.equal(calls,1);
 assert.equal((await readSdkJob(request("/sdk"),e,p.id)).official_sdk,"UNKNOWN");
});
