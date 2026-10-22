# Game Ops 0.4.1 acceptance — 2026-10-21 KST

Status: code, tests, private plugin update and backward-compatible deployment
completed and verified. **End-to-end ChatGPT OAuth and Android support remain blocked.**

## Completed and verified

- Runtime commit `593ead94630e80ba586edb8bd694571fb6ab6fc7` on existing PR #18 branch.
- 57 local tests passed (including 23 OAuth/configuration/HTTP cases); original
  CLI selftest passed 7 assertions. Official SDK tests exercise static QA, exact
  report readback, regression and the existing six-tool surface. OAuth tests use
  generated local IdP signing keys/metadata fixtures, not a real user login.
- Auth failure cases include wrong issuer/audience/owner/scope/signature, expiry,
  missing claims, future not-before, excessive lifetime, attacker-selected key
  URLs, provider outage, incompatible metadata, duplicate headers, hostile Origin
  and oversized requests. Key rotation and default/dual/OAuth modes are tested.
- CI for runtime commit: Game Ops source smoke `39527046280` SUCCESS;
  Forge official SDK v2 verification `39527046310` SUCCESS.
- Existing Railway service `88cf5d7c-bde7-4d06-bd2d-9751c55f428a`, deployment
  `598a6d3a-de90-4df1-9f7c-8bb502499367` reached terminal SUCCESS. Source is pinned
  to the tested runtime commit. Non-source configuration and variable names
  compared unchanged; no secret value or authentication setting was changed.
- Live HTTPS readback: version 0.4.1, `auth_mode=bearer`, `browser=BLOCKED`, health
  200. Anonymous/wrong-key MCP requests and inactive OAuth discovery return 401.
  See `../evidence/oauth-deploy-readback.json`.
- Existing USER/PRIVATE plugin `plugins_6ad5fa125cb08191846ad446225fb5f8` updated
  in place to 0.4.1, release `pluginrel_6ad81448e90881918381729a749aea03`.
  Readback verifies five original skills, default prompts and live bearer MCP
  configuration preserved. Corrected unsupported API-key-in-ChatGPT guidance.
- Mobile fallback login/upload/QA/readback/download/security/UX design is in
  `OAUTH-MOBILE.md`. No mobile interface or additional service was published.

## Not completed / not claimed

| Gate | Current evidence and blocker |
|---|---|
| Production OAuth | Resource-server adapter implemented; no established IdP issuer/resource/immutable owner subject configured in Game Ops. Login/code+PKCE/consent/refresh remain the IdP's responsibility. |
| Registered App mapping | No verified Game Ops App ID available. `.app.json` was not created. Existing plugin ID is not an App ID. |
| ChatGPT web tool call | Cloud Browser at `https://chatgpt.com/plugins` visibly logged out. No actual ChatGPT `run_static_qa`/`get_qa_report` call made. |
| Android app | No physical-device session. Official documentation says custom MCP connection setup is web-only; invocation after web setup still needs a real Android test. |
| Post-deploy authenticated HTTPS regression | Not re-executed: Railway connector returns variable names with values redacted. Existing secret was not regenerated or moved. Local bearer/OAuth SDK checks passed, but do not substitute for a live authenticated call. v0.4.0 remote success is historical evidence only. |
| Mobile-web QA | Designed only, not implemented/deployed/accepted. |

## Required continuation

Configure an established OAuth provider for this resource and the owner's immutable
subject; validate actual authorization-code + S256 behavior, register from signed-in
ChatGPT web, obtain the real App identity, then map the existing PRIVATE plugin and
execute host QA/readback. Keep PR #18 draft and unmerged. Do not enable anonymous
access or publish a fallback to bypass these prerequisites.

See `../evidence/oauth-integration-status.json` and `OAUTH-MOBILE.md` for scope,
settings and official source URLs. Documentation-only evidence commits after the
runtime SHA do not change the pinned deployment.
