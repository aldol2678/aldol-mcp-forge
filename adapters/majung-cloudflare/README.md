# MAJUNG Cloudflare Python Workers candidate (QA Preview tested; production not connected)

This candidate is intentionally based on the still-open MAJUNG PR #22. It does **not** merge, modify main, or reconfigure the deployed MAJUNG Studio.

## Scope and contracts

* Reuses the original enterprise_mcps/majung.py and majung_research.py via a local staging step, with no change to the original files. Only contract-free common helpers are staged.
* Exposes the same three tool names and input/output key sets: research_market, analyze_competitors and evaluate_opportunity.
* Keeps bearer-only /mcp and /status; /healthz is minimal and public. Server secret is required, is not bundled, and must be distinct from every other specialist.
* Paid provider use is deliberately not enabled. Direct source_urls are blocked because the original CPython pinned-socket transport has not been reverified in Workers.
* Live search is **disabled** by default; plain-text market queries correctly return an explicit tool error until MAJUNG_LIVE_ENABLED=true after separate hosted no-key feed tests. Offline supplied sources and the existing two arithmetic tools can be tested without a search provider.
* The revised QA Preview has passed **official Python MCP SDK 2.0.0 auto negotiation, modern tools/list and all three offline tool calls**, plus targeted HTTP header/security checks. This is NOT full protocol conformance certification. SSE subscriptions, MRTR, extensions, Android and ChatGPT client compatibility are not verified. The Studio source snapshot in this Draft PR now supports modern MCP on both inbound and outbound paths; isolated real SDK-to-relay-to-backend calls passed. The **already deployed owner-private Studio still requires a separate reviewed update** before cutover.

## Prepare and validate locally, without cloud credentials

Run from repo root:

```sh
python adapters/majung-cloudflare/prepare.py
python -m unittest discover -s adapters/majung-cloudflare/tests -v
cd adapters/majung-cloudflare
uv run pywrangler dev
```

The final command requires the Python Workers developer tooling. It is not a production deploy and may need internet access for Pyodide/runtime packages.

## Remaining requirements before production cutover

1. Create the **new production-specific** Worker only after QA review, set `ALDOL_MCP_BEARER_TOKEN` as a Cloudflare secret (40-256 printable ASCII characters) using a secret manager; do not add to git.
2. Re-run `/healthz`, bearer 401, modern SDK discovery, tools/list 3 exact names, three offline calls, Origin protections and 512KiB rejection on the new production-specific endpoint; full MCP conformance is not claimed.
3. Independently verify original Python sync networking on Pyodide, DNS/robots/redirect safeguards and original-source provenance **before** enabling `MAJUNG_LIVE_ENABLED`.
4. Compare this patch against the authoritative deployed Sites code, update the actual private Studio only after that review, pin the exact hostname server-side, configure its unique secret, validate real ChatGPT/Android tools, and complete readback before any previous-server cleanup.

## 2026-11-03 official SDK QA evidence

- Python SDK `mcp==2.0.0`, `Client(mode="auto")`, real Cloudflare Preview: **16/16 targeted tests PASS**. The subset includes offline calls for all 3 tools, modern request headers and `_meta`, JSON-RPC result envelopes, version negotiation errors, unauthorized Origins, and fail-closed live search.
- Tested in isolated `aldol-majung-cf-qa` Preview, not on the current Studio. Readback confirmed `workers.dev` and Preview URLs **both disabled** after testing. No production or Railway service was changed.
- [JSON evidence](../../docs/studio-v1/majung-cloudflare-official-sdk-20261103.json) and [optional executable SDK test](tests/test_official_mcp_client.py); requires synthetic QA bearer via `MAJUNG_QA_BEARER`, never commit a token.
- Direct API upload to Cloudflare used `disable_python_external_sdk` because the `workers` SDK was not bundled; normal pywrangler packaging remains a separate build-path check.

**Cutover HOLD:** The source snapshot is patched and isolated real QA E2E now passes, but the deployed private Studio is not updated. Verify a production-specific secret binding and pinned HTTPS host, test actual ChatGPT/Android clients, and keep live search disabled until source-fetch controls are verified.

No Railway service or existing Site is to be deleted to make this work. Do not claim successful migration until live readback is complete.

## 2026-11-03 Studio relay E2E QA

- Isolated Node source tests: **16/16 PASS**. Real Cloudflare QA relay to QA Python backend: **8/8 PASS**. Official `mcp==2.0.0` client through both QA Workers: **6/6 PASS**, including all three offline tools and blocked live search.
- Worker runtime does not support `redirect:'error'`; source now uses `redirect:'manual'` plus explicit 3xx rejection, retaining anti-redirect security.
- Same-zone `workers.dev` Worker-to-Worker `fetch` required the `global_fetch_strictly_public` flag on the *isolated QA relay only*. This does **not** authorize enabling the flag in deployed Sites or production architecture. Service Bindings are the alternative for Cloudflare-internal calls.
- **Cloudflare route readback after QA:** both `aldol-majung-relay-qa` and `aldol-majung-cf-qa` have `workers.dev.enabled=false` and `previews_enabled=false`. The code is retained as a reproducible QA artifact, not a publicly routable service.
- [Non-secret E2E evidence](../../docs/studio-v1/majung-studio-relay-e2e-20261103.json) · [official SDK relay replay](tests/test_official_studio_relay.py). The QA gate must be passed as a synthetic environment variable, never saved to Git.
