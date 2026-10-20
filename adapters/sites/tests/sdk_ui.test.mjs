import test from "node:test";
import assert from "node:assert/strict";
import worker from "../worker/index.js";

const site="https://forge-studio.test";
const req=(path,options={})=>new Request(site+path,{
  ...options,
  headers:{...(options.headers||{}),"oai-authenticated-user-id":"verified-local-tester"},
});

test("served Studio UI includes real SDK verify button and explicit skip state",async()=>{
  const script=await worker.fetch(req("/studio.js"));
  assert.equal(script.status,200);
  const js=await script.text();
  assert.match(js,/공식 SDK 실행 검증/);
  assert.match(js,/SDK 결과 새로고침/);
  assert.match(js,/sdk_verifier_available/);
  assert.ok(js.includes('/sdk'));
  const s=await worker.fetch(req("/api/session"));
  const status=await s.json();
  assert.equal(status.sdk_verifier_available,false);
  assert.equal(status.python_execution,"SKIP");
});
test("SDK status stays SKIP before a configured private host",async()=>{
  const get=await worker.fetch(req("/api/projects/00000000-0000-0000-0000-000000000000/sdk"),{});
  const body=await get.json();
  assert.equal(get.status,200);
  assert.equal(body.available,false);
  assert.equal(body.official_sdk,"SKIP");
});
