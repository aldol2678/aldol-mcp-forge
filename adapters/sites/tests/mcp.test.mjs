import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";
import worker from "../worker/index.js";

const reference = spawnSync(process.env.PYTHON || "python3", [new URL("python_reference.py", import.meta.url).pathname], { encoding: "utf8", maxBuffer: 4_000_000 });
assert.equal(reference.status, 0, reference.stderr);
const { schemas, cases } = JSON.parse(reference.stdout);
const request = (body, extra = {}) => new Request("https://forge.example/mcp", { method: "POST", headers: { "content-type": "application/json", ...extra }, body: typeof body === "string" ? body : JSON.stringify(body) });
const rpc = async (method, params = {}, id = 1) => (await worker.fetch(request({ jsonrpc: "2.0", id, method, params }))).json();

test("Sites discovery, tools/list schema parity and least-privilege annotations", async () => {
  const discovered = await rpc("server/discover");
  assert.deepEqual(discovered.result.supportedVersions, ["2026-07-28"]);
  const listed = await rpc("tools/list");
  assert.equal(listed.result.tools.length, 3);
  for (const tool of listed.result.tools) {
    assert.deepEqual(tool.inputSchema, schemas[tool.name]);
    assert.deepEqual(tool.annotations, { readOnlyHint: true, destructiveHint: false, openWorldHint: false });
  }
  assert.equal((await rpc("initialize")).result.protocolVersion, "2026-07-28");
  assert.deepEqual((await rpc("ping")).result, {});
});

for (const fixture of cases) {
  test("Python parity: " + fixture.label, async () => {
    const response = await rpc("tools/call", { name: fixture.name, arguments: fixture.args });
    assert.equal(response.error, undefined);
    if (Object.hasOwn(fixture, "error")) {
      assert.equal(response.result.isError, true);
      assert.equal(response.result.content[0].text, fixture.error);
      assert.equal(response.result.structuredContent, undefined);
    } else {
      assert.equal(response.result.isError, false);
      assert.deepEqual(response.result.structuredContent, fixture.output);
      assert.deepEqual(JSON.parse(response.result.content[0].text), fixture.output);
    }
  });
}

test("JSON-RPC errors, notifications, IDs and method routing", async () => {
  assert.equal((await worker.fetch(request("{"))).status, 400);
  for (const invalid of [[], null, { method: "tools/list" }, { jsonrpc: "2.0", method: "x", id: {} }]) {
    assert.equal((await (await worker.fetch(request(JSON.stringify(invalid)))).json()).error.code, -32600);
  }
  assert.equal((await worker.fetch(request({ jsonrpc: "2.0", method: "notifications/initialized" }))).status, 202);
  assert.equal((await rpc("missing")).error.code, -32601);
  assert.equal((await rpc("tools/call", { name: "__proto__" })).error.code, -32602);
  assert.equal((await rpc("tools/call", { name: "forge_create", arguments: { project_name: "../../tmp" } })).error.code, -32602);
  assert.equal((await rpc("tools/call", null)).error.code, -32602);
  assert.equal((await rpc("tools/list", {}, "string-id")).id, "string-id");
  assert.equal((await rpc("tools/list", {}, null)).id, null);
  assert.equal((await worker.fetch(new Request("https://forge.example/mcp"))).status, 405);
  assert.equal((await worker.fetch(new Request("https://forge.example/not-found"))).status, 404);
});

test("request bounds, invalid UTF-8, content type and cross-origin refusal", async () => {
  assert.equal((await worker.fetch(request("{}", { origin: "https://evil.example" }))).status, 403);
  assert.equal((await worker.fetch(request("{}", { "content-type": "text/plain" }))).status, 415);
  assert.equal((await worker.fetch(request("{}", { "content-length": "1500001" }))).status, 413);
  assert.equal((await worker.fetch(request("x".repeat(1500001)))).status, 413);
  const invalid = new Request("https://forge.example/mcp", { method: "POST", headers: { "content-type": "application/json" }, body: new Uint8Array([255]) });
  assert.equal((await worker.fetch(invalid)).status, 400);
});

test("no outbound API requests; no shared user input retained between calls", async () => {
  const original = globalThis.fetch;
  let called = 0;
  globalThis.fetch = async () => { called++; throw new Error("Outbound network forbidden"); };
  try {
    for (const identity of ["user-a", "user-b", "user-a"]) {
      const response = await worker.fetch(request({ jsonrpc: "2.0", id: identity, method: "tools/call", params: { name: "forge_preview", arguments: { description: "HTML" } } }, { "oai-authenticated-user-id": identity }));
      assert.equal((await response.json()).result.structuredContent.template, "html_audit");
    }
    const spec = { openapi: "3.0.0", servers: [{ url: "https://do-not-contact.invalid" }], paths: { "/pets": { get: { operationId: "listPets" } } } };
    assert.equal((await rpc("tools/call", { name: "forge_preview_openapi", arguments: { spec_json: JSON.stringify(spec) } })).result.structuredContent.default_network_access, false);
    assert.equal(called, 0);
  } finally { globalThis.fetch = original; }
});

test("deployment manifest has MCP only; read-only core needs no Node/Python/runtime dependencies", async () => {
  const manifest = JSON.parse(await readFile(new URL("../.openai/hosting.json", import.meta.url)));
  assert.deepEqual(manifest.capabilities, ["mcp"]);
  assert.equal(manifest.d1, null);
  assert.equal(manifest.r2, "BUCKET");
  const source = await readFile(new URL("../worker/core.js", import.meta.url), "utf8");
  assert.doesNotMatch(source, /\bimport\s|\brequire\s*\(|\beval\s*\(|new Function\s*\(|\bfetch\s*\(\s*["']/);
});

test("real loopback HTTP tools/list and tools/call for all three tools", async () => {
  const server = createServer(async (incoming, outgoing) => {
    const response = await worker.fetch(new Request(`http://127.0.0.1:${server.address().port}${incoming.url}`, {
      method: incoming.method, headers: incoming.headers,
      body: Readable.toWeb(incoming), duplex: "half",
    }));
    outgoing.writeHead(response.status, Object.fromEntries(response.headers));
    outgoing.end(Buffer.from(await response.arrayBuffer()));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const url = `http://127.0.0.1:${server.address().port}/mcp`;
    const messages = [
      { method: "tools/list", params: {} },
      { method: "tools/call", params: { name: "forge_list_templates", arguments: {} } },
      { method: "tools/call", params: { name: "forge_preview", arguments: { description: "HTML 게임 검사" } } },
      { method: "tools/call", params: { name: "forge_preview_openapi", arguments: { spec_json: JSON.stringify({ openapi: "3.1.0", paths: { "/pets": { get: { operationId: "listPets" } } } }) } } },
    ];
    const responses = [];
    for (const [id, message] of messages.entries()) {
      const response = await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id, ...message }) });
      assert.equal(response.status, 200);
      const body = await response.json();
      assert.equal(body.id, id);
      assert.equal(body.error, undefined);
      responses.push(body.result);
    }
    assert.equal(responses[0].tools.length, 3);
    assert.ok(responses[1].structuredContent.html_audit);
    assert.equal(responses[2].structuredContent.template, "html_audit");
    assert.deepEqual(responses[3].structuredContent.operations, ["listPets"]);
    assert.equal(responses[3].structuredContent.default_network_access, false);
  } finally { await new Promise((resolve) => server.close(resolve)); }
});
