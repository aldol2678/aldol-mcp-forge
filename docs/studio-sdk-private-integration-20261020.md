# Forge Studio SDK verification integration — 2026-10-20

## Result and boundary

The existing owner-private Site is updated in place, using the exact PR #8 ancestry (which already includes PR #7). The SDK verification UI, signed async job bridge, strict ZIP verifier and status recovery are implemented. **The production Python host is NOT connected, and production SDK execution remains SKIP.** This is not a completed production SDK E2E, release or merge.

- Site: https://aldol-forge-readonly-20261020.al-dori.chatgpt.site
- Project ID: `appgprj_6ad6bde7a48881918c1767e3e9f1252f`
- Existing plugin ID: `plugin_asdk_app_sites_62e21d5429008191a9b9c05bb8fe2990`
- Original version: 5, source `9c55236e808cbb05c4977670c3eb7efb2c99d2b8`, deployment `appgdep_6ad6d7848ca88191a8feb893dd7b32d8`
- Intermediate v6 Sites source: `47df68b6ca0b4b3a0f234f0774a55568f039102a` (Sites source repository, separate from GitHub main)
- Audience: custom, sole owner, zero external visitors, access-policy revision 1. No access mutation.
- Manifest preserved: `capabilities: [mcp]`, `r2: BUCKET`, `d1: null`, same project ID. No data migration, overwrite or deletion.
- Sites source repository was opened through its own credential and normal source workflow; GitHub remains a separate MIT project. No GitHub main edits/merges.

## Dependencies

Baseline main was `67b96b99bc1d509537759435258bd8592acf4e0b`, PR #6 merged. PR #7 head was `cc22849fdafec16d5dd7c8add21a4da352f02ac6`; PR #8 head was `db0647f748931e773b1f6e45c428572c24351802`. PR #8 is stacked on #7. This integration branch directly descends from #8; existing changes were not cherry-picked twice or rewritten. A cumulative Draft PR against main contains #7 + #8 + bounded fixes. Do not independently merge overlapping branches without reconciling ancestry. PR #5 is an independent older local bridge, not used or merged here. All existing PR states are retained.

Observed pre-existing CI: #7 runs 39375754589/39375754590 succeeded; #8 run 39377716571 succeeded. No workflow run was returned for the squash main SHA. These CI runs are distinct from this task's local execution and from production.

## Bounded fixes

- Clear separate sections for file integrity and actual SDK execution; saved project selector in verification lab.
- SDK request loading, queued/running labels, mobile full-width controls, result refresh and collapsible execution details.
- Background polling restores from the user-scoped R2 latest-job pointer after reload. A project/generation guard prevents a delayed previous project response from changing the current project's state. Polling does not lock the entire UI.
- Only full authenticated SDK v2 evidence with in-memory + stdio PASS and no network use can produce PASS, on submission as well as polling. An incomplete PASS becomes FAIL. TIMEOUT stays TIMEOUT; interrupted tasks are UNKNOWN.
- Verifier malformed output/process failures are FAIL rather than TIMEOUT. Timeout kills the Python process group, including SDK stdio children. Nested verifier timeouts retain TIMEOUT.
- Deployed Worker validation fetches `/studio.js`, compares exact bytes to `client.js`, parses its syntax and checks button/handler presence. The generated `page.js` is rebuilt before packaging; browser JS cannot contain the server secret.

## Existing host investigation

| Candidate | Current observation | Decision |
|---|---|---|
| Ion environment | Read existing collaboration/DM records. No authenticated persistent verifier HTTPS endpoint or directly callable Ion shell/SSH runtime is exposed to this task. Python 3.12, restart persistence and OS network policy on that machine were not established. | UNKNOWN; not connected, not claimed unavailable globally. |
| Existing Sites | Worker ESM with R2; current env exposes only `FORGE_WRITES_VERIFIED`, no SDK bridge URL/origin/secret. Sites cannot run this Python subprocess server. | Keep current Site for UI/R2; SDK SKIP. |
| Existing Railway | Authenticated `list_projects` returned empty. | No reusable project found; no new paid resource created. |
| Existing Vercel subscription | Current project inventory read; no dedicated Forge SDK worker identified. Existing game/ARAM projects were not changed. Durable process execution, private workspace and SDK network limits were not established for them. | Not selected by assumption. |
| This development runner | Actual Python 3.12.14 + separate `mcp==2.0.0` venv; real loopback tests work. | Ephemeral test runner only, never treated as production hosting. |
| GCP/other subscriptions | No suitable authenticated host management/execution tool or verified verifier endpoint is available here. | Unverified; no deployment or account change. |

To enable later requires an existing approved persistent Python 3.12 host, durable private workspace, `mcp==2.0.0`, authenticated HTTPS proxy, protected HMAC secret, process and outbound-network policy, disk limits and operator-managed lifecycle. Host-side CPU/memory/network isolation is **not proved by local tests**. Exact trusted generator parity plus disabled API settings is not a general OS sandbox. No tunnel, public port, paid server or permission expansion was created.

## Executed local verification

| Check | Actual result |
|---|---|
| Worker/adapter Node tests | 215/215 PASS, including immutable versions, tenant isolation, real eight JSON-RPC tool contracts and status normalization |
| Build artifact | Valid ESM; exact deployed client bytes and SDK event handlers; no client secret |
| Python archive + gateway tests | 13 PASS: real SDK both transports, HMAC/expiry, cross-owner denial, hash/code/traversal rejection, duplicate jobs, restart persistence, process failure vs timeout |
| Whole offline regression suite, SDK-free Python | 26 run: 25 PASS, 1 SKIP (Linux namespace unavailable) |
| Same legacy offline suite in SDK-installed venv | 3 subtest failures because `test_all_templates_generate_smoke_package` hard-codes SDK-not-installed; 2 SKIP. Preserved log; the intended SDK-free suite passes, separate official SDK tests pass. No unrelated tests silently rewritten. |
| Generated Studio projects | Four generated projects accepted by original validator/AST and real SDK memory/stdio |
| Forge Python SDK runtime | Eight tools through real official SDK in-memory + stdio PASS; network_called false |
| Actual Worker HMAC → localhost HTTP → Python SDK → Worker result | PASS, duplicate returns same job ID, refresh reads same result, other user denied; synthetic identity + memory R2 only |
| Browser desktop | Actual create, version addition, lab selection, integrity PASS while SDK remains SKIP, disabled SDK controls, reload selected version restoration |
| Browser 390px / 820px | Responsive lab, saved-project selection, disabled SDK controls and error text; 390px integrity test. Browser emulation/iframe, not real phone or production sign-in. |

Browser QA uses **explicit synthetic identity and in-memory storage**, never production user authentication. Browser logs contained extension metadata errors (`chrome-extension://.../content-script.bundle.js`); these are not app errors. Hosted Site URLs cannot be tested through this managed cloud browser, so production browser sign-in/mobile tests remain unverified.

## Actual production MCP / R2 verification

The already installed existing plugin now exposes all eight tools. All eight were actually invoked successfully against the existing Site; this is distinct from local protocol tests.

- `forge_list_templates`, `forge_preview`, `forge_preview_openapi`: actual private MCP calls PASS.
- `forge_create`: test project `sdk-update-20261020-ark`, id `3ee29ed2-dabc-4ecf-80e1-63da1b911ffd`, version 0.2.0.
- `forge_add_tool`: new id `ee2981ff-5fb0-4081-91ae-02845708cd65`, version 0.2.1, correct parent ID. Original version re-read by `forge_test`, integrity PASS.
- `forge_import_openapi`: test project `sdk-api-20261020-ark`, id `3f26a284-431f-499c-aa8f-342708e9d878`, version 0.3.0, GET only and API default disabled.
- `forge_package`: real private ZIP generated, 15,119 bytes, SHA-256 `4dc5459452fca7a6086c8606d714fb55423a0e4475aa8934862bda511097130b`.
- The returned persisted project was re-packaged **locally** and matched that exact production ZIP hash. Its local SDK 2.0.0 in-memory and stdio verification PASS is in `live-project-local-sdk.json`. This does not claim the production button invoked Python or that the browser downloaded the production ZIP.
- Added test projects/versions remain intact; none deleted. No prior user project was overwritten.

## Remaining completion gate

Production SDK E2E is **SKIP** until an approved persistent HTTPS host is connected. After host setup, validate with the real signed-in owner in the existing Site: stored project → SDK request → host execution → result return → reload and result recovery. Verify actual R2 job pointer and host restart persistence. Do not show local/CI PASS as that production outcome. A later operator decision is needed if hosting requires new paid resources or changes to other services.

## Deployment readback correction

The initial v6 readback proved current browser JS but failed the SDK session/API assertion: four files in the old Sites checkout still differed from the integration checkout (`worker/index.js`, `scripts/bundle.py`, and two legacy test references). v6 is an intermediate deployment, not the completed integration. Every Worker/script/test file was re-written and byte-compared, and the artifact validator now also exercises `/api/session` SDK availability and the real SDK route's anonymous denial. All 215 integration tests and 15 applicable tests in the actual Sites checkout passed. Final deployment/readback identifiers are recorded below when confirmed. No R2 project or access setting was altered by this correction.

Final Site source: `877074f923c7eb60999ae764a3c737b9d6855598`; final deployment ID: `appgdep_6ad71bf90a8c8191b852537e59e19a73`; saved version ID: `appgprj_6ad6bde7a48881918c1767e3e9f1252f~appgver_e5408dfcd4c08191ac4a4fe5d1325c8e`. Terminal deployment/readback evidence will be reported independently.

Final native deployment reached **succeeded**, Site version **7**, has_mcp true, env revision 1. Project/plugin IDs and access-policy revision 1 remain unchanged. Platform service readback confirms exact `/studio.js` parity, SDK session field false and SDK route authentication denial. A platform service credential does not supply a signed-in viewer; its direct `/mcp` request was unauthorized. Installed plugin MCP calls succeed and are recorded separately; do not confuse those auth paths.
