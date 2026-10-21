# Specialist private runtime v1 · 2026-10-21

Status: code and local official SDK transport verified; Railway provisioning BLOCKED. New project creation returned `Free plan resource provision limit exceeded. Please upgrade to provision more resources!`. Only existing personal workspace 253aaf07-905e-490c-9f19-6c0d27e6f1d4 exists with 2 projects. No existing project/service configuration was changed. No upgrade or paid API use was authorized/executed.

PR13 is open Draft/unmerged at 598bb9b1595e10a1c8654d735b46bac335a53174. This is a separate common runtime branch. Existing SEUM implementation and runtime were not changed.

## Running
Use Python3.12 and `pip install -r enterprise_mcps/requirements-studio.txt`, configure independent secret environments, then `python -m enterprise_mcps.specialist_http`. Set `ALDOL_COMPANY=bonsae` or `majung`, independent `ALDOL_MCP_BEARER_TOKEN` values (40..256 ASCII characters), `PORT=8080`, and `ALDOL_PUBLIC_HOST` or Railway-generated `RAILWAY_PUBLIC_DOMAIN`. Never put secrets in Git, client code, plugin packages or messages.

Dockerfile.specialist-mcp uses the official Playwright Python1.58.0 image and pinned Python MCP2.0.0. Its container build is NOT_RUN because Railway creation was blocked; do not call the image build validated. The local Chromium download returned invalid ZIP responses, so browser rendering is also NOT_VERIFIED. The server exposes only its company three tools, authenticated `/mcp` and `/status`, public minimal `/healthz`. Railway edge terminates HTTPS; local transport tests are HTTP loopback only.

## Sites relay
The new owner-private Sites expose exactly the company tools using Sites MCP2026-07-28 and relay to official Python SDK2.0.0. Set server-only Site values `MCP_BACKEND_URL=https://<actual Railway domain>/mcp` and secret `MCP_BACKEND_TOKEN` only after a healthy real deployment. The relay accepts only HTTPS Railway hostnames and fixed MCP path. No backend values are configured currently; tools return explicit unavailable errors.

For BONSAE only, optional `ASSET_FACTORY_TOKEN` is a supported service token for the existing Asset Factory Site. Current cross-Site HTTP authentication check returned401; no token was copied into the new Site. The native connected Asset Factory tool works for metadata only. Never forge the other Site caller identity or remove its authentication to make an adapter work.

For MAJUNG, no-key Bing public RSS is best-effort public retrieval, not an official contracted search API. A supplied Tavily API key is not enough to charge credits: `MAJUNG_SEARCH_ALLOW_CREDIT_USE=true` is additionally required after cost authorization. Neither is configured. Direct source reads require exact operator `MAJUNG_FETCH_ALLOWED_HOSTS`, robots permission, public DNS pinning and no redirects. Source snippets and domain counts do not establish truth or editorial independence.

## Tests
Official MCP2.0.0 in-memory and real stdio9tools/18calls, company-separated real HTTP6calls, unauthenticated/duplicate/cross-company401, body413, unknown-tool/input/route rejection, secret non-disclosure and existing SEUM3tool regression passed locally. Actual remote Railway HTTPS, ChatGPT namespace calls and Android app remain NOT_VERIFIED.

Continue by resolving the Railway account capacity without touching existing projects, create the two approved independent private projects/services, deploy each reviewed company commit, set unique server-only secrets, run remote SDK and security tests, then set Site backend variables and redeploy each exact saved source. Verify actual ChatGPT tools in a new plugin-enabled session and Android separately.
