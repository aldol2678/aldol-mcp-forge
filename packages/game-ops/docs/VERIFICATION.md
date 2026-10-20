# Game Ops v0.4 verification — 2026-10-21 KST

Base checked live: PR #17 merged; main db3cf756dcbcb3e79bfe7cf9c9ffada33c19c60b. Working branch feat/game-ops-mcp-v04-20261021. Original private plugin v0.3.0 release pluginrel_6ad6150fdf6081918e38d771417d5b7d read before update.

## Executed local evidence

- Official Python MCP SDK 2.3.0, real child-process stdio: initialize, all six tools/list, tools/call for actual HTML and ZIP ingestion, static QA PASS and FAIL, persisted QA JSON readback and PASS-to-FAIL regression detection. Invalid path/QA ID/unknown top-level arguments rejected. Normal stdin/transport shutdown succeeds. `evidence/stdio.json`.
- HTTP subprocess with official SDK: unauthenticated/wrong token 401, valid bearer tools/list/call, hostile Origin 403 and oversized request 413. Browser policy UNKNOWN. HTTP refuses host paths. No-token startup fails closed.
- New module tests: 29 PASS. ZIP traversal/absolute paths/Windows drive/backslash, duplicate members, symlink, count and expansion limits; invalid base64/type/hash; expired report cleanup and distinct profile uncertainty. Actual Node parse-only marker test proves uploaded JS does not execute in static checks.
- Original CLI built-in test: 7 assertions PASS (`evidence/cli-selftest.log`).
- Forge Python: 26 tests, OK, 1 pre-existing optional SDK test skipped in base Python (`evidence/forge-python.log`).
- Forge Sites adapter: 207 PASS (`evidence/forge-sites.log`).
- Browser and JSON scenarios attempted through enabled local MCP against our own test fixture. Both UNKNOWN: Chromium executable unavailable. Playwright browser download repeatedly returned an invalid/truncated ZIP; apt install failed on setgroups/setuid permission restrictions. No arbitrary game HTML executed. `evidence/browser.json`.

## Remote acceptance (recorded after deployment)

Railway existing project aldol-seum-mcp-private, production; isolated new service game-ops-mcp-api. Service ID 88cf5d7c-bde7-4d06-bd2d-9751c55f428a. Existing seum-mcp-api is untouched. Endpoint https://game-ops-mcp-api-production.up.railway.app/mcp. Owner bearer secret is injected only into the service, never source or plugin.

See final deployment and live-client evidence added during verification. Source/PR/CI, deployed server, private plugin registration, secure host credential connection, actual host tool call and Android real-device acceptance remain distinct.

## Security and limitations

Single-owner bearer authentication, not OAuth. No multi-tenant service; all reports accessible to the configured owner credential. Uploads bounded to 2 MiB; report retention 24h/128 records, transient filesystem. No guaranteed report durability across deployments. Container non-root and Railway memory/CPU limits configured, but they are not a validated arbitrary-HTML execution sandbox. HTTP browser/scenario execution stays disabled, independent of local flag.

Touch viewports are emulation only. Android ChatGPT credential activation/call is not proven by stdio/HTTP tests or a saved plugin manifest. Remote browser isolation, real device browser checks, durable storage and multi-user authentication remain future work.
