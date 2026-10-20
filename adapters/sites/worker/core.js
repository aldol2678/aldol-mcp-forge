// MIT. Independent Sites adapter for the three read-only Forge operations.
// No filesystem, subprocess, storage, outbound fetch, or code evaluation.
// Platform boundary: Sites dispatch authenticates /mcp and authorizes viewers.
const VERSION = "0.1.0";
const PROTOCOL = "2026-07-28";
const MAX_BODY_BYTES = 1_500_000;
const TEMPLATES = Object.freeze({
  html_audit: "HTML의 기본 문서 구조, 모바일 viewport, 이미지 대체 텍스트를 정적 검사",
  json_audit: "JSON 구문, 최상위 구조, 키 수 검사",
  text_stats: "텍스트 길이, 단어 수, 줄 수 계산",
});
const own = (object, key) => Object.hasOwn(object, key);
const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const length = (value) => [...value].length; // Python len / JSON Schema code points.
const full = (expression, value) => expression.exec(value)?.[0] === value;
const PY_KEYWORDS = new Set([
  "False", "None", "True", "and", "as", "assert", "async", "await", "break",
  "class", "continue", "def", "del", "elif", "else", "except", "finally", "for",
  "from", "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
  "or", "pass", "raise", "return", "try", "while", "with", "yield",
]);
const RESERVED = new Set(["app", "sys", "MCPServer", "OPERATIONS", "call_operation", "Tool", "serve"]);
const PATH_RE = /^\/(?:[A-Za-z0-9_.~-]|\{[A-Za-z_][A-Za-z0-9_]*\}|\/|-|%[a-fA-F0-9]{2})+$/;
const OP_RE = /^[A-Za-z][A-Za-z0-9_]*$/;
const PARAM_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;
function fail(message) { throw new Error(message); }

function preview({ description }) {
  // Python str.strip includes U+001C..001F and excludes JS's U+FEFF.
  const stripped = description.replace(/^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/gu, "");
  if (!stripped || length(stripped) > 2000) fail("description must contain 1..2000 characters");
  // Long s is the casefold/lower difference relevant to the curated keywords.
  const desc = stripped.toLowerCase().replace(/\u017f/gu, "s");
  const groups = [
    ["html_audit", ["html", "웹게임", "웹 게임", "web game", "webpage", "웹페이지"]],
    ["json_audit", ["json", "제이슨"]],
    ["text_stats", ["텍스트", "문장", "단어", "text", "word", "글자"]],
  ];
  const template = groups.find(([, words]) => words.some((word) => desc.includes(word)))?.[0] ?? null;
  return {
    supported: template !== null, template,
    capabilities: template === null ? null : TEMPLATES[template],
    note: "Only three curated, read-only templates supported. No arbitrary code generation.",
  };
}

function previewOpenAPI({ spec_json }) {
  let doc;
  try { doc = JSON.parse(spec_json); }
  catch { fail("OpenAPI specification must be JSON"); }
  // Original re.match with $ accepts exactly one trailing newline in version.
  const version = object(doc) && typeof doc.openapi === "string" ? doc.openapi.replace(/\n$/, "") : "";
  if (!object(doc) || !full(/^3\.(0|1)\.[0-9]+$/, version)) {
    fail("Only OpenAPI 3.0.x or 3.1.x is supported");
  }
  if (own(doc, "info") && !object(doc.info)) fail("OpenAPI info must be an object");
  if (!object(doc.paths) || Object.keys(doc.paths).length > 64) fail("paths must be an object with <=64 entries");
  const operations = [], skipped = [], used = new Set();
  for (const [path, item] of Object.entries(doc.paths)) {
    if (!full(PATH_RE, path) || path.startsWith("//") || path.includes("%") ||
        path.split("/").some((segment) => segment === "." || segment === "..")) {
      fail("Unsupported or unsafe API path");
    }
    if (!object(item) || own(item, "$ref")) fail("Path must be an inline object");
    for (const method of ["post", "put", "patch", "delete", "trace", "head", "options"]) {
      if (own(item, method)) skipped.push({ method: method.toUpperCase(), path, reason: "non-GET excluded" });
    }
    if (!own(item, "get")) continue;
    const op = item.get;
    if (!object(op) || own(op, "$ref")) fail("GET operation must be inline");
    const name = op.operationId;
    if (typeof name !== "string" || !full(OP_RE, name) || PY_KEYWORDS.has(name) ||
        name.startsWith("_") || length(name) > 64 || used.has(name) || RESERVED.has(name)) {
      fail("GET operationId must be unique safe Python identifier");
    }
    used.add(name);
    const pathParams = own(item, "parameters") ? item.parameters : [];
    const opParams = own(op, "parameters") ? op.parameters : [];
    if (!Array.isArray(pathParams) || !Array.isArray(opParams) || pathParams.length + opParams.length > 12) {
      fail("Unsupported GET parameters");
    }
    const pathNames = new Set(), seen = new Set();
    for (const p of [...pathParams, ...opParams]) {
      if (!object(p) || own(p, "$ref") || !["path", "query"].includes(p.in)) {
        fail("Only inline path and query parameters are supported");
      }
      const pn = p.name;
      if (typeof pn !== "string" || !full(PARAM_RE, pn) || PY_KEYWORDS.has(pn) || seen.has(pn)) {
        fail("Parameter name is unsafe or duplicated");
      }
      seen.add(pn);
      const schema = p.schema;
      if (!object(schema) || !["string", "integer", "boolean"].includes(schema.type) || own(schema, "$ref")) {
        fail("Only inline string/integer/boolean parameter schemas supported");
      }
      if (["content", "style", "explode", "allowReserved"].some((key) => own(p, key))) {
        fail("Advanced parameter encoding not supported");
      }
      if (p.in === "path") {
        if (p.required !== true) fail("Path parameters must explicitly be required");
        pathNames.add(pn);
      }
    }
    const placeholders = new Set([...path.matchAll(/\{(\w+)\}/g)].map((match) => match[1]));
    if (placeholders.size !== pathNames.size || [...placeholders].some((name) => !pathNames.has(name))) {
      fail("All URL path placeholders must have matching path parameters");
    }
    operations.push(name);
    if (operations.length > 12) fail("Maximum 12 GET operations per imported project");
  }
  if (!operations.length) fail("No supported GET operations in specification");
  return {
    supported: true, operations, count: operations.length, skipped,
    default_network_access: false,
    limitations: "GET only, inline scalar path/query parameters, JSON document only.",
  };
}

const schema = (properties) => ({ type: "object", properties, required: Object.keys(properties), additionalProperties: false });
const TOOLS = [
  { name: "forge_list_templates", description: "List the supported curated, read-only MCP tool templates.", inputSchema: schema({}), handler: () => ({ ...TEMPLATES }) },
  { name: "forge_preview", description: "Preview a natural language request; this operation creates no files.", inputSchema: schema({ description: { type: "string", minLength: 1, maxLength: 2000 } }), handler: preview },
  { name: "forge_preview_openapi", description: "Preview supported OpenAPI 3.x JSON GET methods without network calls.", inputSchema: schema({ spec_json: { type: "string", minLength: 2, maxLength: 120000 } }), handler: previewOpenAPI },
];

function validate(schema, args) {
  if (!object(args)) fail("arguments must be an object");
  const unknown = Object.keys(args).filter((key) => !own(schema.properties, key)).sort();
  if (unknown.length) fail("unknown argument(s): " + unknown.join(", "));
  for (const key of schema.required) if (!own(args, key)) fail("missing required argument: " + key);
  for (const [key, value] of Object.entries(args)) {
    if (typeof value !== "string") fail(key + " must be string");
    if (length(value) > schema.properties[key].maxLength) fail(key + " too long");
    if (length(value) < schema.properties[key].minLength) fail(key + " too short");
  }
}

const headers = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", "x-content-type-options": "nosniff" };
const json = (value, status = 200) => new Response(JSON.stringify(value), { status, headers });
const rpcError = (id, code, message, status = 200) => json({ jsonrpc: "2.0", id, error: { code, message } }, status);
async function readBounded(request) {
  if (Number(request.headers.get("content-length")) > MAX_BODY_BYTES) fail("Request body too large");
  if (!request.body) return "";
  const reader = request.body.getReader(), chunks = [];
  let total = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > MAX_BODY_BYTES) { await reader.cancel(); fail("Request body too large"); }
    chunks.push(value);
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
}

const core = {
  async fetch(request) {
    const path = new URL(request.url).pathname;
    if (path === "/" && request.method === "GET") {
      return new Response("Legacy Forge adapter", { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "content-security-policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'self' https://chatgpt.com", "x-content-type-options": "nosniff" } });
    }
    if (path !== "/mcp") return json({ error: "Not found" }, 404);
    if (request.method !== "POST") return new Response(null, { status: 405, headers: { ...headers, allow: "POST" } });
    if (!(request.headers.get("content-type") || "").split(";")[0].trim().toLowerCase().endsWith("/json")) {
      return rpcError(null, -32600, "Use application/json", 415);
    }
    const origin = request.headers.get("origin");
    if (origin && origin !== new URL(request.url).origin && origin !== "https://chatgpt.com") {
      return rpcError(null, -32600, "Origin not allowed", 403);
    }
    let raw;
    try { raw = await readBounded(request); }
    catch (error) { return rpcError(null, -32600, error.message === "Request body too large" ? error.message : "Invalid request body", error.message === "Request body too large" ? 413 : 400); }
    let message;
    try { message = JSON.parse(raw); }
    catch { return rpcError(null, -32700, "Parse error", 400); }
    if (!object(message) || message.jsonrpc !== "2.0" || typeof message.method !== "string" ||
        (own(message, "id") && !(message.id === null || typeof message.id === "string" || (typeof message.id === "number" && Number.isFinite(message.id))))) {
      return rpcError(null, -32600, "Invalid Request", 400);
    }
    // Stateless Sites protocol; no global initialization or per-user state.
    if (!own(message, "id")) return new Response(null, { status: 202, headers });
    const { id, method } = message;
    const params = own(message, "params") ? message.params : {};
    if (!object(params)) return rpcError(id, -32602, "params must be an object");
    let result;
    switch (method) {
      case "server/discover":
        result = { supportedVersions: [PROTOCOL], capabilities: { tools: {} }, serverInfo: { name: "aldol-mcp-forge-sites", version: VERSION } };
        break;
      case "initialize":
        result = { protocolVersion: PROTOCOL, capabilities: { tools: { listChanged: false } }, serverInfo: { name: "aldol-mcp-forge-sites", version: VERSION } };
        break;
      case "ping": result = {}; break;
      case "tools/list":
        result = { tools: TOOLS.map(({ handler, ...tool }) => ({ ...tool, annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false } })) };
        break;
      case "tools/call": {
        const tool = TOOLS.find((tool) => tool.name === params.name);
        if (!tool) return rpcError(id, -32602, "Unknown tool");
        try {
          const args = own(params, "arguments") ? params.arguments : {};
          validate(tool.inputSchema, args);
          const output = tool.handler(args);
          result = { content: [{ type: "text", text: JSON.stringify(output) }], structuredContent: output, isError: false };
        } catch (error) {
          result = { isError: true, content: [{ type: "text", text: error.message }] };
        }
        break;
      }
      default: return rpcError(id, -32601, "Method not found");
    }
    return json({ jsonrpc: "2.0", id, result });
  },
};

export { core, TOOLS, preview, previewOpenAPI, validate, readBounded, json };
