# SEUM MCP private Railway operational verification · 2026-10-20

## Deployment identity

- Repository: aldol2678/aldol-mcp-forge
- Implementation PR: #15 (Draft), stacked on #14 and #13.
- Deployed source commit: `dbf3d5d9b0a849d0d028e3fe3f4bc8b65d524493` (pinned).
- Independent Railway project: `aldol-seum-mcp-private`
- Project ID: `5ffa81e3-0133-4bb2-851f-297f42eb730a`
- Service ID: `2a7f6d18-3018-4ee7-a7d0-3f269cf42924`
- Environment ID: `ece4566a-7025-44c9-91d1-ea799b1ccf10`
- Final successful deployment: `4228d390-4d6e-49d1-9c05-77f00817cf20`
- Owner-only Railway project; public network edge is bearer-protected.
- Service host: `seum-mcp-api-production.up.railway.app`; Streamable HTTP path: `/mcp`
- Private token provided exclusively by Railway environment variables. **No token is stored in GitHub or this report.**
- No PR auto-deploys. The Git source is pinned to the verified commit.

## Actual operational observations (not local CI substitutes)

Railway build and deployment status: `SUCCESS` with `mcp==2.0.0`
and one active service.

The production container emitted these three real verification events:

1. `SEUM_LIVE_GITHUB_PROBE status=PASS`: one HTTPS GET through the
   read-only adapter to the public `aldol2678/aldol-mcp-forge`
   `examples/pets_openapi.json` file, validated as Git blob with
   matching SHA and parsed successfully as JSON.
2. The production HTTP server handled multiple real loopback MCP POST
   requests to `/mcp` with response `200 OK`.
3. `SEUM_AUTHENTICATED_HTTP_PROBE status=PASS`: the official MCP SDK
   Streamable HTTP client sent a bearer token over container-local HTTP,
   discovered `analyze_code`, `implement_change`, `review_release`
   and invoked `analyze_code` with a Python source fixture.
   This is **real transport E2E inside the production container**,
   not an internet-external authenticated MCP client.

An independent external browser checked the public HTTPS service:
- `GET /healthz` without authentication -> HTTP `200`,
  `{"service":"seum-mcp","healthy":true}`.
- `GET /mcp` without Authorization -> HTTP `401`,
  `{"error":"authorization_required"}`.
These external checks preceded the final redeploy but used the same
unmodified authentication and health implementations; the final deployment
health check also succeeded.

CI on implementation HEAD: https://github.com/aldol2678/aldol-mcp-forge/actions/runs/39433312873
- Original specialist tests 11/11 PASS
- GitHub read adapter tests 7/7 PASS
- HTTP auth/host checks 4/4 PASS
- True HTTP MCP integration / Bearer 1/1 PASS
- Existing official SDK in-memory and stdio specialist tests PASS

## Preserved boundaries

- ARAM WORLD Railway service checked independently: `SUCCESS`; no modifications.
- Forge Studio v9 remains a separate, unchanged owner-private Site.
- Existing SEUM contract still has exactly three tools; no GitHub write
  scopes or file mutation.
- No GitHub personal access token is configured; only publicly visible
  GitHub files are available. Private repository access is unverified.
- No direct ChatGPT plugin installation, OAuth authorization or *external*
  bearer-authenticated Client E2E was performed; do not claim it.
- Full visual/mobile UI E2E is not relevant to this standalone HTTP API.
- Service compute is Railway-hosted and may incur hosting usage charges.

## Next integration gate

To expose the service as a ChatGPT-accessible MCP plugin, use a supported
private plugin integration with secure OAuth or server-side credential
handling. Do **not** paste the Railway bearer into the plugin manifest or
conversation. First verify the plugin provider's authentication support
and complete a separately authorized installation/connection. Keep the
remote MCP endpoint non-public without bearer verification.
