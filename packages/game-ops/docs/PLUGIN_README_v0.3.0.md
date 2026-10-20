# ALDOL Game Ops v0.3.0 (PRIVATE)

Platform-independent QA workflows **and a bundled offline HTML/ZIP QA runner**. GitHub, CI, PRs and deployment hosts are optional, not prerequisites.

## What actually works

- `scripts/html_qa.py` statically inspects an HTML document / ZIP entry point, checks inline and bundled JavaScript syntax when Node.js is available, records dependency status and SHA-256.
- When Playwright Python + Chromium are installed in a local sandbox: opens HTML via `set_content`, tests responsive overflow and optionally target sizes on 320/360/390px mobile *emulations* and desktop 1365px, collects screenshots, JavaScript page errors, and blocks outside HTTP requests.
- `profiles/jelly-lab-v04.json` illustrates game-specific declarative test steps: player state assertions, breeding, emulated save/restore, combat, reward and six menu tabs.
- With `--baseline previous.html`: runs same profile on old and new artifacts, compares test IDs and reports new failures, fixed failures, missing/new test IDs, and SHA changes. No baseline means regression UNKNOWN.
- JSON outputs under user-specified output directory, original input never modified.

## Commands

```bash
python scripts/html_qa.py /path/to/game.html --output /path/to/qa
python scripts/html_qa.py /path/to/jelly_lab.html --profile profiles/jelly-lab-v04.json --output /path/to/qa
python scripts/html_qa.py /path/to/new_game.html --baseline /path/to/old_game.html --profile /path/to/game_profile.json --output /path/to/regression
```

Dependencies: Python 3.10+; Node.js optional for syntax, Playwright Python and Chromium optional for browser stage. No installation or network is performed. `ALDOL_CHROMIUM` can point to the locally available Chromium executable. Browser unavailable => browser checks UNKNOWN.

## Limits and security

**Plugin Creator installs the skills and script files, not a connected execution MCP tool.** ChatGPT can run the script only when a separate already-available, local-file-capable executor is allowed to access those resources. This version does **not** add remote automation, a hosted API, new permissions or a new persistent server. Runtime browser validation was performed outside the plugin host and does not establish an automatic in-chat plugin invocation contract.

Test sessions load HTML into an `about:blank` document through `page.set_content`, with simulated localStorage, rather than actual file URLs/origins. Direct ZIP-relative CSS/JS/image references are embedded; dynamic imports and complex bundlers are not supported. HTTP requests are aborted in the browser but this **is not a hardened sandbox** against arbitrary script behavior, WebSocket/WebRTC or browser vulnerabilities. Only execute untrusted content inside a separate restricted OS/container process with no secrets and network disabled. Real device, real save persistence, and Production readiness remain UNKNOWN.

Source files are read-only. The script creates evidence only under `--output`, and has no publishing, merge, permission-change, or data-upload actions. All other v0.2 project routing/release gates/AI handoffs remain available.
