# ALDOL UI MCP 0.3.2 operations

The UI document and anti-slop version remains 0.3.2. The operational wrapper adds a private Streamable HTTP transport without changing the seven tool signatures or advisory default.

## Runtime
- Python 3.12; official `mcp==2.3.0`, `uvicorn==0.54.0` (requirements.txt).
- stdio: `python -m ui_core.server`
- HTTP: `UI_MCP_API_KEY=<private 32+ character key> python -m ui_core.http_server`
- Endpoint: `/mcp`; public non-sensitive health response: `/health`.
- Bearer API-key authentication is checked before MCP handling. Missing/incorrect credentials return 401. Startup fails without a sufficiently long key. Keys are never included in the plugin package or source.
- SDK request body limit: 512,000 bytes; application document and markup size limits remain unchanged. DNS-rebinding and Origin checks enabled.
- Railway single replica, stateless HTTP. No persistent user documents, execution of supplied markup, or external stylesheet fetches.
- Railway service `ui-mcp-api` only; root `/packages/ui-mcp`. The shared project also contains unrelated services; do not alter them.

## Reproduce
```
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python tests/sdk_smoke.py
python tests/local_http.py /tmp/ui-mcp-http
```
For remote checks set `MCP_TEST_URL=https://ui-mcp-api-production.up.railway.app/mcp` and `UI_MCP_API_KEY` securely, then run `tests/sdk_smoke.py` and `tests/http_security.py`.
For browser QA install Playwright and Chromium and set `CHROMIUM_EXECUTABLE` to its path. Generate the two example previews through `core.render`, then run `tests/browser_03.py` (CI includes exact commands).

## ChatGPT connection
The private plugin uses API-key authentication with Bearer header. Installation and credential entry are separate from deployment and must be verified in the host. Enter only the key stored in this service's `UI_MCP_API_KEY` variable through the host credential dialog; do not paste it into chat. Remote SDK verification does not establish ChatGPT or Android verification.

## Scope limits
Markup review is heuristic, not full browser CSS analysis. Functional rails and intentional slogans can be waived with a documented reason. React TSX generation alone is not React runtime certification. Android requires actual device verification. Keep PR #19 Draft until remaining required host checks are resolved.
