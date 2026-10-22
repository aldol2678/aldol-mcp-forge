# Android mobile web / PWA

ChatGPT custom MCP apps are web-only. This page does not run inside the ChatGPT Android app and does not claim that limitation was bypassed.

`/mobile/` is a separate client on the same FastAPI app as `/ui/mcp` (8 tools), `/bonsae/mcp` (3 tools), and `/health`. The existing MCP mounts still require `Authorization: Bearer` and a ChatGPT origin. A phone browser that calls those mounts directly is rejected before a tool runs.

## What the page calls

The run button performs three in-process MCP `call_tool` invocations, in order:

1. BONSAE `generate_design_spec`
2. UI `ui_import_bonsae`
3. UI `ui_generate` with `target=web-html` and `quality_mode=advisory`

`analyze_design`, `review_visual`, and the other UI tools are listed and marked as not connected to this page. The generated preview is structural card placeholders. States, interactions, accessibility, motion, and responsive layout text stay in the NOT_IMPLEMENTED report. The preview response has its script removed, and the iframe has an empty sandbox.

## Credential

The browser bundle does not contain the key and does not use `localStorage` or `sessionStorage`. The password field is cleared after submit. The server compares it to `ALDOL_DESIGN_MCP_KEY` and sets an HttpOnly, SameSite=Strict cookie scoped to `/mobile` for 30 minutes. The cookie is an expiry and HMAC, not the key. Cross-site requests are rejected.

No new secret is introduced. The existing Vercel variable is reused and is not read into Git. Application code does not log the session body. A platform access log could still record a request path; it should not be given the raw key.

An unauthenticated open proxy is intentionally not provided. The fixed preview URL remains bearer-protected.

## Local check

```bash
pip install -r requirements.txt 'uvicorn' 'httpx'
export ALDOL_DESIGN_MCP_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
python tests/test_mobile_pwa.py
python tests/mobile_mcp_http.py
python -m playwright install --with-deps chromium
python tests/mobile_browser.py
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/mobile/` at a phone width. The key exists only in that process.

## Not claimed

- Authenticated `tools/list` or `tools/call` against the deployed preview. This environment cannot read the Vercel secret.
- A physical Android device, Play install, or home-screen install.
- Production promotion, DNS, or a change to Deployment Protection.
- Railway, `main`, or drafts #19, #21, #27, and #28.
