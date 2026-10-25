# OAuth and mobile integration — 0.4.1

## Decision and current boundary (2026-10-21 KST)

The existing plugin `plugins_6ad5fa125cb08191846ad446225fb5f8` is USER/PRIVATE.
PR #18 remains draft and unmerged. Its original HEAD was
`c127a1dfc2e563c8877ec80125503532034e047e`.

Two independent blockers explain the reported desktop-only/no-auth UI:

1. The current package has `mcp.json` and `.mcp.json`, but no verified registered
   ChatGPT App dependency. A remote URL alone does not create that dependency.
2. Its server accepts a fixed bearer key. ChatGPT's custom-MCP linking flow does
   not present customer API keys. Changing a manifest to say OAuth does not
   convert the server or register an app.

The new code implements the **resource-server half** of OAuth 2.1 integration.
An established authorization provider must supply login, owner consent,
authorization-code + S256 PKCE, exact redirect allowlisting, client registration
(CIMD/DCR or a predefined client), and refresh-token rotation/revocation. No
password form, custom authorization server, or token-minting shortcut was added.
No provider or owner identity was invented. Production activation is blocked
until those real settings and a real owner-issued token are available.

## Implemented contract

- `GAME_OPS_AUTH_MODE=bearer` is the unchanged default. The existing secret is
  required; no OAuth discovery is advertised. This is the deployment's current mode.
- `dual` requires both the existing bearer secret and the complete OAuth config.
  It accepts either a valid owner API key or a valid owner OAuth access token.
- `oauth` accepts only OAuth access tokens; a legacy key is rejected even when
  still present in the environment. This final cutover follows real host acceptance.
- Required config: `GAME_OPS_OAUTH_ISSUER` (exact HTTPS issuer),
  `GAME_OPS_OAUTH_RESOURCE` (exact public HTTPS `/mcp` URL), and
  `GAME_OPS_OAUTH_OWNER_SUB` (immutable IdP subject, not an email or display name).
- Active OAuth publishes `/.well-known/oauth-protected-resource/mcp` and a root
  alias. Only public auth metadata is anonymous; MCP list/call/report requests
  continue to require authentication. 401 includes the resource-metadata challenge.
- Provider discovery uses RFC 8414's issuer-path form, with OIDC discovery as a
  404-only fallback. Issuer must match exactly, S256/code and `gameops:use` must
  be advertised. Authorization/token/JWKS endpoints must be HTTPS and same-origin
  as the issuer in this adapter. Redirects and oversized metadata are rejected.
- JWT verification uses PyJWT/cryptography, fixed RS256/ES256 algorithms, a trusted
  provider JWKS, exact issuer/audience/owner subject, expiry/issued-at/not-before,
  required `gameops:use` scope and a maximum 1-hour access-token lifetime.
  Audience arrays are refused. JWT-provided key URLs/keys/critical extensions are
  refused. This adapter requires signed JWT access tokens; opaque tokens are not supported.
- JWKS cache lasts 5 minutes; new-kid refreshes/outage retries are limited to one
  per 30 seconds. An outage fails closed; it never grants anonymous access.
- Each of the same six MCP tools declares OAuth scopes in `_meta.securitySchemes`
  and the top-level `securitySchemes` wire field when OAuth mode is active.
- No token is stored in plugin files, URLs, browser storage, report JSON or logs.
  Single-owner reports, upload caps, timeouts, non-root execution and remote
  browser/scenario blocking remain in force.

## Activation sequence — not yet executed

1. Configure an established IdP application/API for this exact resource and scope.
   Enable authorization-code + S256 (reject plain/missing PKCE), single-use codes,
   consent, refresh-token rotation/reuse detection, exact callback validation and
   issuer identification where supported. Restrict access to the owner in the IdP
   as well as the resource server. Verify a real token's immutable subject securely.
   Do not reuse another ALDOL service's audience, client secret or owner mapping.
2. Set the three OAuth variables only on the existing Game Ops Railway service,
   set `GAME_OPS_AUTH_MODE=dual`, retain `GAME_OPS_TOKEN`, and deploy the tested SHA.
   Verify discovery, all negative checks, an owner OAuth call, report readback and
   legacy compatibility. No IdP secrets are needed in the resource server.
3. In signed-in ChatGPT web, Plugins → + → Add custom MCP server. Use the existing
   HTTPS `/mcp` endpoint and OAuth. Select the registration method actually supported
   by the IdP. Copy the precise callback displayed by that interface into the IdP;
   do not guess a stable callback when issuer-identification support is absent.
4. Capture the real app technical ID from the registration response/management UI.
   Distinguish the `plugin_asdk_app...` plugin wrapper from the underlying
   `asdk_app...` app dependency. Use backend-resolved app identity; do not infer or
   fabricate it. Only then add `.app.json` and the manifest app reference to the
   existing PRIVATE plugin. Preserve its ID, scope, all five skills and prompts.
5. Update active plugin MCP auth from API-key to OAuth with the verified IdP client
   configuration. Until step 2 is real, keep the package consistent with the live
   bearer mode; an OAuth example is not an active package declaration.
6. In a new ChatGPT web conversation, invoke `run_static_qa` on a small HTML fixture,
   then `get_qa_report` using the returned ID. Compare the complete JSON and record
   host-visible tool evidence plus server evidence. SDK-only tests do not satisfy this.
7. Switch to `oauth` only after acceptance and an explicit migration decision for
   any existing machine clients. Validate legacy-key rejection and owner OAuth again.

## Android status and acceptance

Official help currently states that connecting custom MCP servers is **web only**.
This is a connection/setup limitation; it does not prove that every registered
app can or cannot subsequently be invoked on Android. The current package has no
verified app mapping. No physical Android session is available to this agent.
Therefore Android invocation is **UNKNOWN / NOT ACCEPTED**, not supported.

Required real-device evidence: app/OS version, installed plugin identity, plugin
visible in composer, completed owner authorization if prompted, actual static QA
call and matching report readback. Chrome desktop mode, a responsive viewport,
API tests and documentation are not substitutes. Do not claim an SDK test is a
ChatGPT web or Android test.

## Authenticated mobile-web fallback — design only, not deployed

Preferred deployment: `/qa` on the existing Railway service after approval and
IdP configuration; no new public service or new audience. A separate owner-private
Sites frontend could be considered only if explicitly approved later.

Flow: owner login → select `.html`/`.zip` (2 MiB) → inspect/static QA → results →
reopen report by ID → compare two reports → download JSON → sign out.

- Backend-for-frontend login with code + S256, server-side OAuth tokens and short
  owner-bound sessions; `Secure`, `HttpOnly`, `SameSite=Lax` session cookie with
  rotation. Exact callback, state/nonce checks, CSRF token + exact Origin checks
  for every modifying POST. Never put GAME_OPS_TOKEN in mobile JavaScript.
- Gate the page, API and report downloads by the same immutable owner subject.
  No anonymous report endpoints or bearer values in query strings/localStorage.
- Server-side QA API reuses `QAService`, so the same limits and browser UNKNOWN
  decisions apply. It must not relax the MCP endpoint's Origin rejection.
- Render report fields with textContent/escaped text; never render uploaded game
  HTML or untrusted report markup. Download JSON as an attachment with no-store.
- 360–430 px one-column screen, >=44 px tap targets, file name/size before upload,
  accessible progress/status, explicit expired-report state, retry only after
  checking operation status. Backend idempotency key prevents duplicate work.
- No service worker caching of reports/session data. Show the 24-hour/128-report
  ephemeral retention limit and static-only scope next to results.
- Acceptance: Android Chrome on the physical device, unauthenticated/other-user
  denial, CSRF/logout expiry checks, upload→QA→readback→download. Design completion
  is not implementation or mobile support completion.

## Sources checked

- https://developers.openai.com/plugins/build/auth
- https://developers.openai.com/plugins/build/plugins
- https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt

The previous README/verification directions to paste an owner API key into a
ChatGPT credential prompt were incorrect for this connection flow and are superseded.
