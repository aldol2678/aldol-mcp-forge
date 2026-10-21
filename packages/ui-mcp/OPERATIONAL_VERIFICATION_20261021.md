# ALDOL UI MCP 0.3.2 operational integration — 2026-10-21 KST

Overall: **BLOCKED for complete ChatGPT integration**; server implementation and SDK transport checks passed.

## Source provenance
- PR #19 baseline: `0362dd192fa1944cb7b8aed4c35502607da94e9b`.
- Both Library v0.3.2 ZIP copies share SHA256 `0ebb6328aec463a09de81dce8b3f27077b41095621cfa90ab381f68cebbf36c3`.
- All 22 individual files from `ALDOL UI MCP v0.3.2 Source` match the baseline PR files. The ZIP additionally contains historical browser results.
- Original v0.3.1 ZIP SHA256 `9614c69506fb0f89d5e68308d7d1628cd40198d935afb5ee46a011aa8deaefb5` preserved.
- Accessible Drive search returned no matching named source documents; the connector's MIME filters do not prove absence of ZIPs. GitHub and Library establish the working source.

## Changes
- Official SDK 2.3.0 dependency and private Streamable HTTP wrapper; 512 KB body ceiling, strict Bearer authentication, DNS rebinding and Origin checks, non-root Docker image, health route.
- Excessively nested JSON converted into validation failure.
- Found real React runtime crash: exported `spec` was already the root node, but render used `spec.root`. Corrected to `make(spec, "0")` and added a real browser consumer regression.
- Added SDK transport, HTTP security and UI CI checks. Advisory default, enforce high-severity block, reasoned waivers, seven tool signatures and schema versions remain unchanged.
- Plugin package contains endpoint and API-key scheme, never credentials.

## Executed evidence (separate from historical 68/8 results)
| Check | Result |
|---|---|
| Python unit regressions | PASS 71/71 |
| Official SDK stdio | PASS 27 scenarios; all 7 tools and schemas |
| Official SDK local HTTP | PASS 27 scenarios |
| Local HTTP security | PASS 6/6: missing/wrong key, malformed JSON, body limit, hostile Origin and Host |
| Chromium web/HUD | PASS 8/8: 360/390/768/1280, overflow, targets, toggle, Escape, bindings, actions, no page errors |
| Real React consumer | PASS: bundle, mount, toggle, Escape, host values/actions, 390px overflow and page errors |
| Railway first operational deployment | SUCCESS `da0f7932-a3db-4c74-ac4c-c2860d5e3547`, source `26a9743df322a793fbe3fc7a5fcad3803cfdd6ad` |
| Remote HTTPS SDK on first deployment | PASS 27/27; discovery, normal/invalid input, advisory/enforce, waivers and reconnect |
| Remote HTTPS security on first deployment | PASS 5/5 (Host rebinding test local only) |
| First operational commit CI | PASS Forge verification + UI MCP integration |
| Final React-fix deployment/CI | Must be read back after this commit; final delivery evidence records the actual result |
| ChatGPT private plugin creation/configuration | PASS: USER scope, PRIVATE, v0.3.2, API-key Bearer config read back |
| ChatGPT installation/authentication/tools | BLOCKED: host reports not_installed, no UI MCP tools exposed in current conversation |
| Android device | UNKNOWN: no actual device test |

## Deployment boundaries
- Project `5ffa81e3-0133-4bb2-851f-297f42eb730a`, environment `ece4566a-7025-44c9-91d1-ea799b1ccf10`.
- New independent service `06540fb4-3a03-4b73-943c-fcc7c61027bb` (`ui-mcp-api`); other services not modified.
- https://ui-mcp-api-production.up.railway.app/mcp ; `Authorization: Bearer <UI_MCP_API_KEY>`.
- Source commit pinned; ordinary branch pushes do not silently change the deployment. Roll forward only after validation by reconnecting the exact commit.
- Public health endpoint is not permission to inspect or generate UI. All MCP requests require authentication.

## Host handoff
Private plugin: https://chatgpt.com/plugins/plugins_6ad810ca2dd08191a4a44e8dc1bc68c6
Plugin ID: `plugins_6ad810ca2dd08191a4a44e8dc1bc68c6`
User must install/connect and enter the UI service's `UI_MCP_API_KEY` in the host credential dialog. No key is included here. Then call ui_review and ui_review_markup from ChatGPT, verify a valid existing document, violation, normal UI and access policy. A remote SDK call is not proof of a ChatGPT call.

Do not merge or mark full operational integration complete until required host checks pass. No public sharing or unrelated service changes were performed.
