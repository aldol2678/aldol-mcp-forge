# MAJUNG OAuth MCP Gateway (not yet authorized for live use)

Uses pinned `@cloudflare/workers-oauth-provider@1.1.0`. Two JS Workers and the existing Python Worker are separated:
- `aldol-majung-auth`: authorization server, Cloudflare Access **must** protect `/authorize` with owner-only email; also fails closed unless `ctx.access` verifies identity. Consent is explicit and bound to browser by the provider library; DCR and PKCE handled by the provider.
- `aldol-majung-oauth`: public MCP gateway; OAuthResourceServer checks token resource, scope `mcp:read` and authenticated principal, forwards via Cloudflare Service Binding, never public HTTP, to the existing Python backend.
- `aldol-majung-mcp`: original Python backend, retains Bearer, live external search disabled. Do NOT remove its secret or replace its source during this phase.

Backend credentials, `OAUTH_SECRET`, access policy and KV binding are set in Cloudflare only. No test secrets, owner email or tokens in GitHub.

## Deployment gates

1. Obtain and review the source package; bundle Cloudflare OAuth library with source lock and build reproducibility.
2. Create dedicated `OAUTH_KV` and Access policy tied to a verified owner identity, not public /anonymous registration. Verify effective Access enforcement on **GET and POST /authorize**.
3. Add Auth Worker `OAUTH_KV`, `OAUTH_SECRET`, `ISSUER`, `MCP_SERVER_URL`; only the auth worker owns user grants and token signing.
4. Add gateway Service Bindings `AUTH_SERVER` (AuthServer exported entrypoint) and `MAJUNG_BACKEND` (Python Worker). Add `BACKEND_BEARER` secret that matches private Python Worker. Never expose bearer in logs or responses.
5. Verify OAuth metadata, DCR, PKCE S256 enforcement, approval login gate, deny/replay/tampered token, token audience, tool calls, expiry/refresh, no unauthorized access, and mobile ChatGPT registration.
6. Do not change old installed Sites plugin until live connection works. No live search enablement by OAuth migration.

**NOT SAFE to enable token grants until Access policy, consent, and SDK end-to-end are independently verified.**
