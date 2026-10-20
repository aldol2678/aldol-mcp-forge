# ALDOL MCP Forge × ChatGPT Sites — implementation and evidence

Date: 2026-10-20 (Asia/Seoul). This is a development integration, not a Forge release.

## Result

The owner-private Site is deployed and an actual private plugin has been
provisioned and installed. The three read-only Forge tools have an independent
JavaScript implementation with Python differential and HTTP protocol tests.

**End-to-end ChatGPT tool invocation verified on 2026-10-20 (Asia/Seoul).**
A subsequent ChatGPT conversation exposed the provisioned
`ALDOL MCP Forge · Read-only` plugin tool namespace and actually invoked all
three tools. `forge_list_templates` returned the expected HTML/JSON/text
templates; `forge_preview` with `description="HTML 게임 검사"` returned
`supported=true`, `template="html_audit"`; `forge_preview_openapi` with
a single GET `listGames` returned `count=1`, `operations=["listGames"]`,
`default_network_access=false`. All three tool calls returned usable
structured results, not merely installation metadata.
Sites' own authenticated platform requests previously returned HTTP 200 for
`server/discover` and `tools/list`. The **older** direct service-credential
request received HTTP 401 at `/mcp`, which is still correctly recorded as a
failed request through a different authentication path. No authentication
bypass, public-access expansion or host deployment was needed. This
ChatGPT invocation was observed through the connected plugin; it is not
evidence of the five unimplemented write tools working.

## Source baseline and CI

- Repository: https://github.com/aldol2678/aldol-mcp-forge
- Inspected `main`: `5c200bd7ed4d3f2508631fcd785378dd2ccc3666`.
- PR #2 (official Python SDK entrypoint) and PR #3 (Inspector CLI) were already
  merged when inspected; this work does not merge or alter them.
- Main run https://github.com/aldol2678/aldol-mcp-forge/actions/runs/39348245461
  succeeded. All four jobs succeeded: offline regression, generated-server SDK,
  Forge SDK runtime and independent Inspector CLI.
- Existing `forge.py`, `forge_sdk.py`, `templates.py`, `openapi_forge.py`, `verify_sdk.py`,
  `ci/`, `tests/` and the existing workflow are unchanged.

## Sites compatibility

SUPPORTED means the current Sites contract provides the capability; the evidence
column distinguishes live execution from documentation. LIMITED is a restricted
subset. UNKNOWN means the exact capability has not been established.

| Requirement | Status | Evidence and practical boundary |
| --- | --- | --- |
| Create and host an MCP server | SUPPORTED | This private Worker deployment succeeded with `has_mcp: true`; platform `server/discover` and `tools/list` returned 200. |
| HTTPS MCP endpoint | SUPPORTED | Actual endpoint returned by `get_site` below; OAuth resource also returned. |
| MCP authentication | SUPPORTED | Sites owns authentication/viewer checks; owner-only policy read back with zero external visitors. Authenticated platform discovery/list succeeded. Direct service credential test got 401; this is not an OAuth connection test. |
| Existing Python MCP SDK v2 entrypoint directly in Sites | UNSUPPORTED | The supported Site server build is JavaScript Worker ESM/Vinext on Cloudflare Workers. Sites exposes no Python process launcher for `forge_sdk.py`. This does not claim Cloudflare products in general have no Python support. |
| File generation and reading | LIMITED | JS can generate bytes and read request/bundled data; Sites documents R2 for durable files. It does not expose the existing Python project filesystem contract. File generation/storage tools are not implemented here. |
| ZIP packaging | UNKNOWN | JS byte packaging is technically feasible; no Sites ZIP implementation or runtime ZIP test was performed. Existing Python ZIP + SDK verification requires a Python execution host. |
| Persistent file storage | SUPPORTED (documented) | Current Sites storage reference explicitly supports logical `r2` bindings. No R2 resource was provisioned or exercised; manifest value is null. |
| Database | SUPPORTED (documented) | Current Sites storage reference explicitly supports `d1` bindings and managed schema migrations. No D1 resource was provisioned or exercised; manifest value is null. |
| External process / Python subprocess | UNSUPPORTED | No supported process-execution surface exists in the Site Worker runtime. Development-container subprocess access is separate and was not treated as hosted capability. |
| Register actual MCP tools as a ChatGPT plugin | SUPPORTED (three read-only tools live-tested) | Sites provisioned the private plugin and the subsequent ChatGPT conversation successfully invoked all three read-only tools. The five write/test/package tools are not exposed. |
| Separate private non-production preview | UNKNOWN / unavailable in selected starter | The managed preview reference says the Worker ESM starter has no preview entrypoint. Every Sites deployment URL is production, including owner-private URLs. This implementation uses owner-private publication; public publication was not performed. |

Capability sources read from the installed official Sites package `1.0.1`:
`skills/sites/SKILL.md`, `references/site-mcp-server.md`, `references/storage.md`,
`references/identity-and-secrets.md`, `references/preview/managed.md`,
`templates/worker-esm-starter/README.md`. These are platform-provided local
references, not assumptions based on similarly named external services.

## Implemented tools and tests

| Tool | Implementation | Local HTTP `tools/call` | Live Sites ChatGPT call |
| --- | --- | --- | --- |
| `forge_list_templates` | Existing three-template mapping | Passed | PASS: returned HTML/JSON/text templates |
| `forge_preview` | Original keyword order, output and input bounds | Passed; HTML → `html_audit` | PASS: HTML 게임 검사 → `html_audit` |
| `forge_preview_openapi` | Original restricted JSON GET preview validation/output | Passed; sample operations discovered; network false | PASS: `listGames`, count 1, no network |

`adapters/sites/worker/index.js` is self-contained, dependency-free Worker ESM.
It implements stateless MCP `2026-07-28` discovery/list/call and compatibility
initialize/notification/ping. It declares all tools read-only, rejects extra
arguments, invalid JSON, wrong types, invalid lengths, unsafe OpenAPI paths,
unsupported GET parameters and duplicate operation IDs. Errors remain visible
through MCP `isError: true`.

Tests completed:

- **175/175** adapter tests passed. This includes **169 Python differential cases**,
  schema parity, JSON-RPC protocol/HTTP errors, notification silence, code-point
  limits, request byte limits, malformed UTF-8, cross-origin refusal, identity
  input independence, no-outbound-network assertions, deployment artifact
  contract, and actual loopback HTTP list/call for all three tools.
- Original Python regression: **26 tests run, 25 passed, 1 skipped, 0 failures**.
  Skip reason: Linux user/mount/network namespaces are unavailable in this
  container. No claim of namespace sandbox validation is made.
- Worker artifact build and ESM validation passed. No npm/pip packages were
  installed for the adapter tests.
- The current container does not have official `mcp` installed; existing SDK/Inspector
  evidence is from the inspected main CI, and the new PR runs those existing jobs
  again. Local Node parity tests are not called official Python SDK validation.
- Hosted platform logs record authenticated discovery and list with HTTP 200.
  The direct remote verification log from the first private publication records HTTP 401 and remains a failed **service-credential** request; this does not contradict the separately verified ChatGPT plugin calls. The second publication only tightened Python-equivalent regular-expression full matching; authentication is unchanged.

Evidence: [adapter TAP](evidence/sites-20261020/sites-tests.tap),
[Python regression](evidence/sites-20261020/forge-regression.log),
[deployment, policy and sanitized Worker events](evidence/sites-20261020/sites-platform.json),
[remote authentication test](evidence/sites-20261020/remote-verification.json).
Headers, source write credentials and service tokens are excluded from evidence.

The new `verify-sites-adapter.yml` workflow runs parity/protocol tests and Worker
build validation on relevant PR changes. The existing four-job workflow remains
unchanged. CI evidence for this branch is the actual PR's run, not the baseline run.

## Deployed connection

- Site: https://aldol-forge-readonly-20261020.al-dori.chatgpt.site
- MCP: https://aldol-forge-readonly-20261020.al-dori.chatgpt.site/mcp
- OAuth resource: same MCP URL (returned by Sites, not guessed).
- Site ID: `appgprj_6ad6bde7a48881918c1767e3e9f1252f`.
- Deployment: `appgdep_6ad6bfe4f7c481918f3df73c51a027aa`.
- Saved version: `appgprj_6ad6bde7a48881918c1767e3e9f1252f~appgver_f880b9c2f1c08191b9e2977b278710d3`.
- Private plugin: `plugin_asdk_app_sites_62e21d5429008191a9b9c05bb8fe2990`.
- Sites source commit: `cf427564e81108663d745aa7a4b6c66d5d2483ae` (private deployment
  repository; separate from the upstream GitHub branch).

Use **Plugins → Personal → Created by you → ALDOL MCP Forge · Read-only**.
The three listed tools were subsequently observed and successfully called from
a ChatGPT conversation on 2026-10-20. In a different conversation, the user may
need to select/connect this same already provisioned plugin to expose its tools.
Reuse this plugin; no second app, public endpoint or paid host is needed.

Read-only verification prompts:

1. `ALDOL MCP Forge의 forge_list_templates를 실제 호출해줘.`
2. `forge_preview를 description="HTML 게임 검사"로 실제 호출해줘.`
3. `forge_preview_openapi를 아래 JSON 문자열로 호출해줘.`

```json
{"openapi":"3.1.0","info":{"title":"Demo","version":"1.0"},"paths":{"/pets":{"get":{"operationId":"listPets"}}}}
```

The third tool's input is **`spec_json` containing a JSON string**, not a URL or
an already-parsed object. Expected output includes `operations: ["listPets"]`,
`count: 1` and `default_network_access: false`. Live success returns from all three tools have now been observed in ChatGPT.
This validates the read-only adapter only, not the five Python-dependent tools.

## Future extension: smallest change to existing Forge

No extra server is needed for the three preview tools. Preserving full Python
generation/test behavior requires a trusted Python execution host; first assess
an already-owned host rather than creating Railway or another paid resource.

| Future tool | Sites-side feasible work | Python bridge boundary |
| --- | --- | --- |
| `forge_create` | Validate request; reserve user-owned project ID | Call existing curated generator in a fresh workspace; refuse collisions |
| `forge_add_tool` | Resolve owned project and expected revision | Existing backup/checksum/pre-commit validation; per-project lock |
| `forge_test` | Read user-owned job status/results | Existing compile, checksum, compatibility and official SDK tests |
| `forge_package` | Authorized download metadata; later R2 artifact storage | Existing test-first ZIP generation and hash verification |
| `forge_import_openapi` | Existing preview and schema rejection | Existing GET-only generator with dry-run defaults |

Proposed bridge (not implemented or deployed):

- Sites authenticates the user and resolves a server-owned workspace/project ID.
  Derive storage keys from the Site-scoped authenticated user ID and generated
  opaque IDs. Do not accept an arbitrary workspace root or raw filesystem path.
- Send only allowlisted operations and validated fields over an authenticated
  HTTPS job API to a trusted existing Python worker. The worker maps IDs to
  preconfigured directories, checks containment and symlinks, uses exclusive
  creation/per-project locks, and refuses overwrites. Service credentials without
  an authenticated user identity cannot initiate user-owned mutations.
- Reuse `forge.py` / `forge_sdk.py` core functions instead of rewriting them.
  Isolate process execution with bounded time/output and a suitable worker
  account. Existing environment workspace configuration alone is not a sandbox.
- Keep remote API configuration empty and prohibit arbitrary shell/source input.
  SDK/compile/smoke tests remain separate statuses; never replace executed Python
  tests with JavaScript schema validation.
- Return job IDs, approved artifact IDs, SHA256 and execution evidence. Add D1/R2
  only when persistent jobs/artifacts are actually implemented. No storage has
  been provisioned by this integration.

No paid resources, public Site access or formal releases were performed by
this integration. At the original Work handoff, the PR was unmerged and main
unchanged. After subsequent direct ChatGPT tool invocations, the result is:
**owner-private deployment and all three ChatGPT `tools/call` invocations
verified**; Python generation, write/test and packaging remain unimplemented
in the Sites adapter. The PR's actual merge status is tracked on GitHub.
