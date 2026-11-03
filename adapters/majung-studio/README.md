# ALDOL MAJUNG Studio

This is a **source snapshot**, not a live edit of the privately deployed MAJUNG Site. The recorded deployment and authoritative Sites source identifier are in `docs/studio-v1/majung-deployment.json`. No real credentials belong in Git.

Run `npm run build` before preview/validation. `npm run dev` is for Sites supervised preview; `/__qa/390`, `/__qa/820` and `/__qa/1280` are responsive iframe checks, not Android emulation.

## Cloudflare MCP relay candidate

The Draft PR #38 snapshot adds MCP protocol `2026-07-28` outbound metadata/mirrored headers, preserves the unrelated legacy Asset Factory transport, retains headerless legacy Sites clients, and adds modern `/mcp` discovery/list/call response envelopes.

On 2026-11-03, Node source tests were **16/16 PASS**, real QA relay-to-backend HTTP tests **8/8 PASS**, and official MCP Python SDK 2.0.0 through QA relay and backend **6/6 PASS**. All QA `workers.dev` and Preview URLs were disabled again and verified. Evidence: `docs/studio-v1/majung-studio-relay-e2e-20261103.json`.

This is **not** a live Sites deployment. The existing private Site remains disconnected unless its authoritative source is reviewed, patched, deployed and read back with production-specific server-only `MCP_BACKEND_URL`, `MCP_BACKEND_ALLOWED_HOST` and `MCP_BACKEND_TOKEN`. Do not reuse synthetic QA tokens, switch other MCP servers, enable live search or claim ChatGPT Android compatibility without separate validation.
