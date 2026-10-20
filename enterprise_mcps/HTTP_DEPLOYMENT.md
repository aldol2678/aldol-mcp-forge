# Private SEUM MCP remote runtime (Railway)

This deployment is separate from ARAM WORLD, INHA WORLD and Forge Studio v9.
The only public unauthenticated route is GET /healthz (no source details).
GET /status and all requests to /mcp require a 40..256 char bearer secret.

## Security and setup

1. Deploy branch feat/seum-private-http-mcp-runtime from aldol2678/aldol-mcp-forge
   into its OWN private Railway project, not an existing game/project service.
2. Set a strong random ALDOL_SEUM_MCP_BEARER_TOKEN as a server-only env variable.
3. Set ALDOL_SEUM_GITHUB_READ_ENABLED=1 to allow read-only public GitHub file GET.
   Set ALDOL_SEUM_STARTUP_PROBE_ENABLED=1 only for the public, documented
   smoke file in examples/pets_openapi.json. No secrets are needed for this.
4. After a service domain is assigned set ALDOL_SEUM_PUBLIC_HOST to the exact
   assigned hostname, with no scheme/path. The official MCP SDK host allowlist
   remains active; unlisted hosts receive 421.
5. Optional private-repo support: ALDOL_SEUM_GITHUB_TOKEN as a server-side
   GitHub token restricted to repository Contents:read. Never log, expose,
   paste into chat or store in source.
6. Connect the private client to https://<exact-host>/mcp with Authorization:
   Bearer <secret>. Bearer auth is transport protection, NOT user OAuth. Do not
   share this service URL + token or install it as a public ChatGPT plugin.
7. Verify health 200 without auth; /mcp returns 401 without bearer;
   authorized /status records startup_probe.status==PASS after a genuine
   public GitHub API GET, with the Git blob SHA and SHA-256.
8. Run official Python MCP v2 Client(streamable_http_client(...)) using a
   server-side bearer header and call analyze_code on a public small .py/.json
   file. Observe github_provenance with method github-readonly-static.
9. Keep single replica. Do not enable GitHub writes, command execution, PR
   auto-deploys, or unrelated Cloud Run/Slack credentials.

Environment setup MUST fail closed without a secret. Public GitHub fetch is
opt-in. GitHub file reads use fixed https://api.github.com, no redirects or
proxy forwarding, max 3500 bytes, and Git blob SHA verification. No remote
MCP user account authorization beyond the single bearer secret is provided.
For multi-user or broader public access, implement OAuth + rate limiting
before expanding permissions.

Deployment of this feature branch does not merge PR #14 or change Site v9.
