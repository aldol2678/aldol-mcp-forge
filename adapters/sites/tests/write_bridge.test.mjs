import test from "node:test";
import assert from "node:assert/strict";
import {callVerifiedForgeWriteTool, MUTATING_FORGE_TOOLS} from "../bridge/write-client.mjs";

const ctx = {verifiedBySites: true, subject: "owner-id", writeApproved: true};
const conf = {
  bridgeUrl: "https://private-bridge.example/v1/execute",
  bridgeOrigin: "https://private-bridge.example",
  bridgeSecret: "a".repeat(48),
  ownerSubject: "owner-id",
};
const operation = {tool: "forge_create", arguments: {
  project_name: "secure-html", description: "HTML 게임 검사",
}};

test("declares five only in nondeployed bridge module", () => {
  assert.equal(Object.keys(MUTATING_FORGE_TOOLS).length, 5);
  assert.ok(!("forge_preview" in MUTATING_FORGE_TOOLS));
});

test("authenticated user with explicit write approval sends scoped request", async () => {
  let calls = 0;
  const fakeFetch = async (url, req) => {
    calls++;
    assert.equal(url.href, conf.bridgeUrl);
    assert.equal(req.method, "POST");
    assert.equal(req.headers["X-Forge-Bridge-Secret"], conf.bridgeSecret);
    const request = JSON.parse(req.body);
    assert.deepEqual(Object.keys(request).sort(), ["arguments", "tool"]);
    assert.deepEqual(request, operation);
    assert.equal("subject" in request, false);
    assert.equal("workspace_root" in request, false);
    return {
      status: 200, redirected: false,
      text: async () => JSON.stringify({ok: true, result: {created: true}}),
    };
  };
  const result = await callVerifiedForgeWriteTool(operation, ctx, conf, fakeFetch);
  assert.deepEqual(result, {created: true});
  assert.equal(calls, 1);
});

test("fails closed before networking on unverified, wrong owner or unapproved writes", async () => {
  for (const bad of [
    {...ctx, verifiedBySites: false},
    {...ctx, subject: "other-id"},
    {...ctx, writeApproved: false},
    {subject: "owner-id"},
    null,
  ]) {
    let calls = 0;
    await assert.rejects(
      callVerifiedForgeWriteTool(operation, bad, conf, async () => { calls++; }),
      /Verified owner identity/,
    );
    assert.equal(calls, 0);
  }
});

test("never connects to HTTP, other hosts, missing secret or caller-selected endpoint", async () => {
  for (const cfg of [
    {...conf, bridgeUrl: "http://private-bridge.example/v1/execute"},
    {...conf, bridgeUrl: "https://wrong.example/v1/execute"},
    {...conf, bridgeUrl: "https://private-bridge.example/admin"},
    {...conf, bridgeUrl: "https://private-bridge.example/v1/execute?next=1"},
    {...conf, bridgeSecret: "short"},
  ]) {
    let calls = 0;
    await assert.rejects(callVerifiedForgeWriteTool(operation, ctx, cfg,
      async () => { calls++; }));
    assert.equal(calls, 0);
  }
});

test("rejects unsupported tools, invalid schemas and path-like project names", async () => {
  const cases = [
    {tool: "forge_shell", arguments: operation.arguments},
    {tool: "forge_create", arguments: {project_name: "safe-html"}},
    {tool: "forge_create", arguments: {...operation.arguments, owner: "other"}},
    {tool: "forge_create", arguments: {...operation.arguments, project_name: "../bad"}},
    {tool: "forge_create", arguments: {...operation.arguments, description: "x".repeat(2001)}},
    {tool: "forge_test", arguments: {project_name: "safe-html", isolation: "unsafe"}},
    {tool: "forge_import_openapi", arguments: {project_name: "demo-api", spec_json: "{"}},
  ];
  for (const value of cases) {
    let calls = 0;
    await assert.rejects(callVerifiedForgeWriteTool(value, ctx, conf,
      async () => { calls++; }));
    assert.equal(calls, 0);
  }
});

test("refuses remote failure, redirects, or malformed success JSON", async () => {
  for (const res of [
    {status: 401, redirected: false, text: async () => "{}"},
    {status: 200, redirected: true, text: async () => "{}"},
    {status: 200, redirected: false, text: async () => '{"ok":false,"error":"Denied"}'},
    {status: 200, redirected: false, text: async () => "not JSON"},
  ]) {
    await assert.rejects(callVerifiedForgeWriteTool(operation, ctx, conf, async () => res));
  }
});
