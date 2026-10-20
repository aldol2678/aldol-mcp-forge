import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const projectRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const workerPath = resolve(projectRoot, "dist/server/index.js");
const manifestPath = resolve(projectRoot, "dist/.openai/hosting.json");

const [source, manifest] = await Promise.all([
  readFile(workerPath, "utf8"),
  readFile(manifestPath, "utf8"),
]);
JSON.parse(manifest);

// A data URL forces ESM parsing even though the generated output has no package.json.
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const workerModule = await import(moduleUrl);
assert.equal(
  typeof workerModule.default?.fetch,
  "function",
  `${pathToFileURL(workerPath)} must export default.fetch`,
);

const sessionResponse = await workerModule.default.fetch(new Request("https://forge.test/api/session"));
const session = await sessionResponse.json();
assert.equal(session.sdk_verifier_available, false, "SDK backend/session must be bundled");
const sdkResponse = await workerModule.default.fetch(new Request("https://forge.test/api/projects/00000000-0000-0000-0000-000000000000/sdk"));
assert.equal(sdkResponse.status, 403, "SDK endpoint must exist and reject missing identity");
const client = await readFile(resolve(projectRoot, "worker/client.js"), "utf8");
const response = await workerModule.default.fetch(new Request("https://forge.test/studio.js"));
assert.equal(await response.text(), client, "Deployed JS must equal client.js");
const {Script} = await import("node:vm");
new Script(client);
for (const marker of ["sdk-project", "run-sdk", "refresh-sdk", "pollSdk", "공식 SDK 실행 검증"])
  assert.ok(client.includes(marker), "SDK UI/handler missing: " + marker);
assert.equal(client.includes("SDK_BRIDGE_SECRET"), false, "No server secret in browser script");
console.log("Artifact ESM, served JS parity, SDK handlers and browser syntax PASS");
