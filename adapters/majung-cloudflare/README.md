# MAJUNG Cloudflare Python Workers candidate (not deployed)

This candidate is intentionally based on the still-open MAJUNG PR #22. It does **not** merge, modify main, or reconfigure the deployed MAJUNG Studio.

## Scope and contracts

* Reuses the original enterprise_mcps/majung.py and majung_research.py via a local staging step, with no change to the original files. Only contract-free common helpers are staged.
* Exposes the same three tool names and input/output key sets: research_market, analyze_competitors and evaluate_opportunity.
* Keeps bearer-only /mcp and /status; /healthz is minimal and public. Server secret is required, is not bundled, and must be distinct from every other specialist.
* Paid provider use is deliberately not enabled. Direct source_urls are blocked because the original CPython pinned-socket transport has not been reverified in Workers.
* Live search is **disabled** by default; plain-text market queries correctly return an explicit tool error until MAJUNG_LIVE_ENABLED=true after separate hosted no-key feed tests. Offline supplied sources and the existing two arithmetic tools can be tested without a search provider.
* This is a minimal JSON-RPC Streamable HTTP-shaped adapter consistent with the existing Sites relay, **not yet an official SDK v2 compliance claim**. Stateful HTTP, SSE, multiple-protocol-version and Android client compatibility have NOT been verified.

## Prepare and validate locally, without cloud credentials

Run from repo root:

```sh
python adapters/majung-cloudflare/prepare.py
python -m unittest discover -s adapters/majung-cloudflare/tests -v
cd adapters/majung-cloudflare
uv run pywrangler dev
```

The final command requires the Python Workers developer tooling. It is not a production deploy and may need internet access for Pyodide/runtime packages.

## After local tests, required before cutover

1. Create the **new isolated** Worker only, set `ALDOL_MCP_BEARER_TOKEN` as a Cloudflare secret (40-256 printable ASCII characters) using a secret manager; do not add to git.
2. Verify /healthz, unauthenticated /mcp denial, authenticated initialize, tools/list 3 exact names, offline three calls, CORS/origin behavior and 512KiB rejection on the real `workers.dev` address.
3. Independently verify original Python sync networking on Pyodide, DNS/robots/redirect safeguards and original-source provenance **before** enabling `MAJUNG_LIVE_ENABLED`.
4. Add the **exact** Worker hostname to the deployed Sites server-only `MCP_BACKEND_ALLOWED_HOST`, together with the corresponding `MCP_BACKEND_URL` and `MCP_BACKEND_TOKEN`; validate real ChatGPT tools and Android before any cleanup.

No Railway service or existing Site is to be deleted to make this work. Do not claim successful migration until live readback is complete.
