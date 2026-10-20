// Run against one already-authorized Site. Credentials enter via hidden stdin.
// Nothing here is deployed. Never print authentication headers or redirect URLs.
import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { createInterface } from "node:readline";
// Disable PTY echo before asking for credentials. Piped stdin is also supported.
if (process.stdin.isTTY) process.stdin.setRawMode(true);
const lines = createInterface({ input: process.stdin, terminal: false });
console.log("Ready for remote verification JSON on stdin (input is hidden).");
let config;
for await (const line of lines) { config = JSON.parse(line); break; }
lines.close();
assert.ok(config?.url?.startsWith("https://"));
const endpoint = new URL(config.url);
assert.equal(endpoint.pathname, "/mcp");
const auth = config.token ? { "OAI-Sites-Authorization": `Bearer ${config.token}` } : {};
const rows = [];
async function rpc(method, params = {}, id = rows.length + 1) {
  const response = await fetch(endpoint, {
    method: "POST", headers: { "content-type": "application/json", accept: "application/json, text/event-stream", ...auth },
    body: JSON.stringify({ jsonrpc: "2.0", id, method, params }), redirect: "manual", signal: AbortSignal.timeout(20000),
  });
  assert.equal(response.status, 200, `${method}: HTTP ${response.status}`);
  const body = await response.json();
  assert.equal(body.id, id);
  assert.equal(body.error, undefined, JSON.stringify(body.error));
  rows.push({ method, ...(params.name ? { tool: params.name } : {}), status: response.status, response: body });
  return body.result;
}
let report;
let anonymousStatus;
try {
  const anonymous = await fetch(endpoint, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 0, method: "tools/list" }), redirect: "manual", signal: AbortSignal.timeout(20000) });
  anonymousStatus = anonymous.status;
  assert.ok([301, 302, 303, 307, 308, 401, 403].includes(anonymous.status), `private Site accepted anonymous: ${anonymous.status}`);
  assert.deepEqual((await rpc("server/discover")).supportedVersions, ["2026-07-28"]);
  assert.equal((await rpc("initialize")).serverInfo.name, "aldol-mcp-forge-sites");
  const names = (await rpc("tools/list")).tools.map((tool) => tool.name);
  assert.deepEqual(names, ["forge_list_templates", "forge_preview", "forge_preview_openapi"]);
  const templates = await rpc("tools/call", { name: "forge_list_templates", arguments: {} });
  assert.equal(templates.isError, false);
  assert.ok(templates.structuredContent.html_audit);
  const preview = await rpc("tools/call", { name: "forge_preview", arguments: { description: "HTML 게임 검사" } });
  assert.equal(preview.structuredContent.template, "html_audit");
  const spec = await readFile(new URL("../../../examples/pets_openapi.json", import.meta.url), "utf8");
  const api = await rpc("tools/call", { name: "forge_preview_openapi", arguments: { spec_json: spec } });
  assert.equal(api.structuredContent.count, 2);
  assert.equal(api.structuredContent.default_network_access, false);
  const invalid = await rpc("tools/call", { name: "forge_preview", arguments: { description: "html", extra: true } });
  assert.equal(invalid.isError, true);
  report = { passed: true, checked_at: new Date().toISOString(), endpoint: endpoint.href, transport: "HTTPS JSON-RPC", access: "owner-private Sites service credential; not a ChatGPT plugin tool invocation", anonymous_status: anonymous.status, tools_called: names, rows };
} catch (error) {
  report = { passed: false, checked_at: new Date().toISOString(), endpoint: endpoint.href, anonymous_status: anonymousStatus, error: error.message, cause_code: error.cause?.code, rows };
  process.exitCode = 1;
}
if (config.output) await writeFile(config.output, JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report));
if (process.stdin.isTTY) process.stdin.setRawMode(false);
process.stdin.destroy();
