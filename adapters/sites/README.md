# ALDOL MCP Forge Studio (Sites)

Owner-private Worker app and MCP endpoint. Existing three read-only tool contracts are retained in `worker/core.js`; Studio adds deterministic Python project generation, immutable version storage in Sites R2, checksum verification and real ZIP export. No Python execution, subprocess, shell, external fetch, deployment or secret handling happens in the Worker.

## Build and check

```sh
node --test tests/*.test.mjs
bash scripts/build.sh
node scripts/validate-artifact.mjs
```

From repository root: `python adapters/sites/tests/verify_generated.py --official-sdk` runs original Forge validators and real official SDK clients on JS-generated artifacts (requires `mcp==2.0.0`). `python scripts/sync-assets.py` must be run from the repository checkout when original Python assets change; vendored assets are committed. `page.js` is generated from `page.html`, `client.js` and `style.css`. The custom dependency-free bundle contains all runtime modules.

## Identity and writes

Sites dispatch authenticates incoming requests and supplies the Site-scoped `oai-authenticated-user-id`. Never put this Worker behind an untrusted proxy that accepts client-supplied identity headers. Browser POST requires exact same-origin Origin. `/mcp` retains original Origin, MIME, bounded body and JSON-RPC validation. No identity comes from tool arguments.

R2 binding: `BUCKET`. D1 is not needed for this bounded immutable document model. Each user prefix is `studio/v1/SHA256(siteScopedUserId)/`. Random UUID object keys are generated server-side, never supplied as filesystem paths. Name reservations use conditional put; failed saves retain reservations to prevent ambiguous duplicate retries. Adding a tool creates a new immutable object linked to its parent. There is no delete endpoint. The 100-version workspace limit is a capacity guard, not a distributed billing quota.

`FORGE_WRITES_VERIFIED=1` must be set only after platform-authenticated identity forwarding and storage binding have been checked. Without it, persistence mutation routes reject writes and five Studio MCP tools are not advertised. A service bypass token grants no user identity and cannot read/write user records. Code-only preview does not persist data.

## Tools

- `forge_list_templates`, `forge_preview`, `forge_preview_openapi`: unchanged read-only contracts. Website `/api/rpc` invokes the exact same handlers and MCP envelopes.
- `forge_create`, `forge_import_openapi`: generate and save files, **no Python execution**. Extra property rejection and original bounds are enforced.
- `forge_add_tool`: curated template addition as a new version, no arbitrary code/schema editing. Uses `project_id` (Sites immutable UUID) and `template`; deliberately differs from Python Forge's path-based interface.
- `forge_test`: file checksums only; `python_execution` and `official_sdk` are **SKIP**.
- `forge_package`: actual ZIP bytes/CRC-32/SHA-256 and owner-authenticated download path, no public URL.

OpenAPI import retains original GET validation. Generation additionally requires string summary/description; preview retains original compatibility. Source files are byte-compared to original Python generation excluding timestamp-dependent manifest. All API projects are dry-run by default.

## Preview

`npm run dev` starts a **local-only QA harness**, with simulated identity and memory storage. It is not bundled into production and proves nothing about hosted authentication/R2. `/__qa/mobile` and `/__qa/tablet` embed the app at 390/820 CSS pixels for responsive browser QA. Production has no such routes and never injects identity.

## Storage and exports

The R2 project JSON includes metadata and generated file contents. ZIP is generated on demand; download requires the same user identity. It includes original Python files, requirements, README, manifest, client config, explicit validation statuses, SHA256SUMS; archive hash is returned in `X-Content-SHA256`. No ZIP object is publicly published. Browser storage holds only selected project ID as a navigation preference.
