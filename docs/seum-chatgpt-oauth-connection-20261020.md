# ALDOL SEUM ↔ ChatGPT private OAuth integration · 2026-10-20

## State

- Railway service `seum-mcp-api` within isolated `aldol-seum-mcp-private` project
- Railway OAuth deployment `752963c6-b31b-4c48-8811-61526bf46eb3`: **SUCCESS**
- Deployed source commit `a10fb47428e063de321476585bc73c1a7e367421`
- HTTPS remote MCP `https://seum-mcp-api-production.up.railway.app/mcp`
- Plugin **aldol-seum v0.2.0**, original private personal plugin identity preserved:
  `plugins_6ad773be18ac8191981f9a2a4cac4e67`
- Plugin connection manifest `.mcp.json` declares remote MCP server with `oauth`,
  DCR `client.mode=dcr`, token and registration URLs, `seum:read` and `offline_access`
- PR #16: `feat/seum-owner-oauth-21-chatgpt` stacked on PR #15, Draft, **not merged**.

## Verified

- Official SDK / local test CI on PR #16:
  https://github.com/aldol2678/aldol-mcp-forge/actions/runs/39438128179
  (OAuth metadata, ChatGPT-only callback validation, DCR, S256 PKCE, CSRF,
  explicit owner approval form, one-time auth code consumption, refresh rotation,
  protected ASGI status, existing fixed bearer compatibility).
- Railway deployed SUCCESS with new OAuth feature enabled and strong independent
  owner password and signing key in service variables. Existing machine bearer
  remains valid; no secret is in the plugin bundle.
- Independent browser read of live HTTPS public discovery endpoints confirmed
  HTTP 200 for `/.well-known/oauth-authorization-server`,
  `/.well-known/oauth-protected-resource` and `/healthz`.
  Discovery advertises S256, DCR endpoint and matching issuer/resource.
- Plugin Creator update: `aldol-seum v0.2.0` created in place with
  `.codex-plugin/plugin.json` and `.mcp.json` present on readback.
- Existing Forge Studio v9, ARAM WORLD, main branch, other enterprises unchanged.

## REQUIRED owner action (not completed by agent)

1. Open https://chatgpt.com/plugins/plugins_6ad773be18ac8191981f9a2a4cac4e67
   in ChatGPT and use the remote MCP connection/Connect control.
2. In the **SEUM HTTPS OAuth approval page**, enter the server-only owner
   approval password from Railway's `seum-mcp-api` service variable
   `ALDOL_SEUM_OAUTH_OWNER_PASSWORD` (or replace that variable with a new,
   strong owner-chosen secret and redeploy). Do not send it via ChatGPT.
3. Approve the scoped `seum:read` access. OAuth code exchange is PKCE-S256;
   the remote SEUM MCP accepts scoped short-lived tokens.
4. Start a fresh ChatGPT conversation and test `analyze_code` on a benign
   public Python or JSON file. Confirm actual MCP tool listing and call result.

**No client-authorized live ChatGPT MCP tool call has been verified.**
Plugin update and remote OAuth metadata alone do not prove client connection.

## Limitations

- OAuth credentials/codes/access and refresh tokens are held in memory, single
  replica. A Railway container restart invalidates them and requires re-linking.
- Only ChatGPT callback URLs are accepted by DCR; only explicit owner password
  approval issues OAuth codes. Multiple users are not supported.
- GitHub adapter remains read-only and bounded; source changes, merges, deployments
  and paid actions are not exposed.
