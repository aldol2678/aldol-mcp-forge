// Not deployed or registered as an MCP tool.
// Boundary adapter for a FUTURE authenticated Sites-to-Python service call.
// Until Sites exposes a verified viewer identity and a configured private
// backend, all writes fail closed without sending requests.
export const MUTATING_FORGE_TOOLS = Object.freeze({
  forge_create: { required: ["project_name", "description"], optional: [] },
  forge_add_tool: { required: ["project_name", "description"], optional: ["isolation"] },
  forge_test: { required: ["project_name"], optional: ["isolation"] },
  forge_package: { required: ["project_name"], optional: ["isolation"] },
  forge_import_openapi: { required: ["project_name", "spec_json"], optional: ["isolation"] },
});

function validateToolCall(name, args) {
  const fields = MUTATING_FORGE_TOOLS[name];
  if (!fields || !args || typeof args !== "object" || Array.isArray(args)) {
    throw new Error("Unsupported Forge tool or arguments");
  }
  const allowed = [...fields.required, ...fields.optional];
  if (fields.required.some((key) => !Object.hasOwn(args, key)) ||
      Object.keys(args).some((key) => !allowed.includes(key))) {
    throw new Error("Missing or unrecognized tool arguments");
  }
  for (const [key, value] of Object.entries(args)) {
    if (typeof value !== "string") throw new Error(key + " must be string");
    const length = [...value].length;
    const [min, max] = key === "spec_json" ? [2, 120000]
      : key === "description" ? [1, 2000] : [1, 40];
    if (length < min || length > max) throw new Error(key + " length invalid");
  }
  if (!/^[a-z][a-z0-9-]{2,39}$/.test(args.project_name)) throw new Error("Unsafe project name");
  if ("isolation" in args && !["auto", "strict"].includes(args.isolation)) {
    throw new Error("Invalid isolation");
  }
}

function checkTrustedContext(ctx, config) {
  // Never derive viewer identity from MCP tool arguments, URL query params,
  // browser headers or model-provided JSON.
  if (ctx?.verifiedBySites !== true || typeof ctx?.subject !== "string" ||
      !ctx.subject || ctx?.writeApproved !== true ||
      typeof config?.ownerSubject !== "string" ||
      ctx.subject !== config.ownerSubject) {
    throw new Error("Verified owner identity and write approval are required");
  }
  if (typeof config.bridgeSecret !== "string" || config.bridgeSecret.length < 32 ||
      typeof config.bridgeUrl !== "string" || typeof config.bridgeOrigin !== "string") {
    throw new Error("Private bridge is not configured");
  }
  const url = new URL(config.bridgeUrl);
  if (url.protocol !== "https:" || url.pathname !== "/v1/execute" ||
      url.search || url.hash || url.username || url.password ||
      url.origin !== config.bridgeOrigin) {
    throw new Error("Private HTTPS bridge endpoint is not allowlisted");
  }
  return url;
}

export async function callVerifiedForgeWriteTool(
  { tool, arguments: args }, trustedContext, privateConfig, fetchImpl = fetch,
) {
  validateToolCall(tool, args);
  const url = checkTrustedContext(trustedContext, privateConfig);
  // No automatic retries for writes. User identity comes from fixed bridge
  // host configuration, not from the serialized JSON payload.
  const response = await fetchImpl(url, {
    method: "POST",
    redirect: "manual",
    headers: {
      "Content-Type": "application/json",
      "X-Forge-Bridge-Secret": privateConfig.bridgeSecret,
    },
    body: JSON.stringify({ tool, arguments: args }),
    signal: AbortSignal.timeout(110000),
  });
  if (response.status !== 200 || response.redirected) {
    throw new Error("Trusted Python bridge returned HTTP " + response.status);
  }
  const text = await response.text();
  if (text.length > 200000) throw new Error("Bridge response too large");
  const parsed = JSON.parse(text);
  if (parsed?.ok !== true || !parsed.result || typeof parsed.result !== "object") {
    throw new Error("Bridge returned unsuccessful tool execution");
  }
  return parsed.result;
}
