// Exercise the EXACT Studio Worker generator/exporter instead of Python Forge.
// This creates fixture ZIPs without any storage or deployment.
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { generate } from "../adapters/sites/worker/generator.js";
import { packageProject } from "../adapters/sites/worker/store.js";

const output = resolve(process.argv[2] || "ci-results/studio-sdk-fixtures");
await mkdir(output, { recursive: true });

const cases = [
  ["studio-curated-v021", await generate(
    { project_name: "studio-ci-curated", description: "HTML 게임 검사" },
    ["html_audit", "json_audit"],
    { version: "0.2.0", hash: "0".repeat(64) },
  )],
  ["studio-openapi-get", await generate({
    project_name: "studio-ci-openapi",
    spec_json: JSON.stringify({
      openapi: "3.1.0",
      info: { title: "Studio SDK CI", version: "1.0.0" },
      paths: {
        "/pets": {
          get: {
            operationId: "listPets",
            summary: "List pets safely",
            responses: { "200": { description: "OK" } },
          },
        },
      },
    }),
  })],
];

for (const [filename, project] of cases) {
  const result = await packageProject(project);
  const path = resolve(output, filename + ".zip");
  await writeFile(path, result.bytes);
  console.log(JSON.stringify({
    fixture: filename,
    path,
    project: project.project_name,
    version: project.version,
    bytes: result.bytes.length,
    sha256: result.sha256,
  }));
}
