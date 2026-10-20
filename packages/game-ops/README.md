# ALDOL Game Ops MCP v0.4.0

MIT game artifact QA toolkit and an **official Python MCP SDK server**. Reuses the recovered v0.3 CLI without changing Forge runtime. Stdio executes local QA; authenticated Streamable HTTP provides bounded static QA. No new repository is necessary: the module and dependencies remain isolated here.

## Install and run

Python 3.11+ and Node.js 18+ (JS syntax checks). No Node means JS checks are UNKNOWN.

```sh
cd packages/game-ops
python -m venv .venv
.venv/bin/pip install -r requirements.txt
mkdir -p artifacts reports
GAME_OPS_ARTIFACT_ROOT="$PWD/artifacts" GAME_OPS_REPORT_ROOT="$PWD/reports" .venv/bin/python server.py
```

Use `examples/mcp-stdio.json` with your absolute paths. Existing CLI is preserved:

```sh
python scripts/selftest.py
python scripts/html_qa.py examples/demo.html --output /tmp/gameops-cli
```

## MCP tools

| Tool | Input | Result |
|---|---|---|
| `inspect_game_artifact` | `artifact` | Bounded file/ZIP metadata and per-file SHA-256 |
| `run_static_qa` | `artifact` | HTML, JS syntax and bundled resource checks |
| `run_browser_qa` | `artifact`, optional `profile` | Local responsive/44px configured touch-target checks and JS errors |
| `run_game_scenarios` | `artifact`, `profile` | Local game-specific JSON steps |
| `compare_game_versions` | `baseline_id`, `candidate_id` | Conservative comparison of stored QA reports |
| `get_qa_report` | `qa_id` | Exact persisted JSON readback |

Artifact is `{ "filename": "index.html", "content_base64": "..." }`, optionally `expected_sha256`. Stdio additionally accepts `{ "filename":"index.html", "path":"game/index.html" }` relative to the operator-configured artifact root. Exactly one input source. No URL fetching. HTTP never accepts filesystem paths.

Example SDK client (see executable integration tests for full lifecycle):

```python
import asyncio, base64, sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    async with stdio_client(StdioServerParameters(command=sys.executable, args=["server.py"])) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(await session.list_tools())
            result = await session.call_tool("run_static_qa", {"artifact": {
                "filename": "demo.html",
                "content_base64": base64.b64encode(Path("examples/demo.html").read_bytes()).decode()
            }})
            print(result)
asyncio.run(main())
```

## Local browser/scenario execution

Disabled by default. Only a trusted local operator may set `GAME_OPS_ALLOW_BROWSER=1` in an appropriate execution environment. Install `playwright` and Chromium separately and set `ALDOL_CHROMIUM` to its executable. **That flag is consent to run trusted local HTML, not proof of sandboxing.** The inherited runner launches Chromium with `--no-sandbox`; arbitrary/untrusted HTML needs OS/container isolation, no secrets, denied network and resource limits established outside this package. The MCP wrapper does not certify those properties. HTTP ignores this flag and never executes HTML, even when configured to allow local browser runs.

Profiles use the existing `viewports`, `responsive_tabs`, `touch_targets`, `scenarios` keys. Scenario actions: click/tap/fill/select/wait, assert_count/text/visible/state/storage_key, reload_simulated. No evaluate action. Screenshots are disabled in the MCP wrapper; use the CLI for local screenshot files. The old CLI supports larger limits and lacks HTTP path protections; never expose it as a network handler.

## Authenticated remote server

```sh
# Inject a random >=32-character GAME_OPS_TOKEN through your secret manager.
# Never commit it, put it in plugin files, or send it in a URL.
GAME_OPS_PUBLIC_HOST=your-verified-host.example .venv/bin/python server.py --http
```

`/mcp` requires `Authorization: Bearer <owner token>` on **every** request; all unauthenticated discovery/calls are rejected. `/healthz` only exposes service version and the browser-blocked state. Browser Origin headers are refused. Configure the exact host via Railway's `RAILWAY_PUBLIC_DOMAIN` or `GAME_OPS_PUBLIC_HOST`. No OAuth claim is made: use a client supporting bearer headers or ChatGPT API-key authentication.

`Dockerfile` runs as UID 10001, includes Node for parse-only JS checking, excludes Playwright/Chromium. Railway: root `/packages/game-ops`, Dockerfile `Dockerfile`, port 8000, health `/healthz`, one replica, 0.5 vCPU / 0.5 GiB. Only the new service's configuration is changed. `examples/mcp-http.json` describes the connection without containing credentials. In ChatGPT, configure the API key in the connection's secure credential prompt. Package registration alone is **not** a successful ChatGPT connection.

## Evidence and verdicts

Reports distinguish PASS / FAIL / UNKNOWN. Static PASS only covers executed static checks; browser/real-device coverage remains UNKNOWN. Browser policy blocks, unavailable Chromium, empty scenarios, worker failure and timeout are UNKNOWN. Invalid input is a protocol tool error rather than fabricated QA success. Inspection PASS certifies ingestion/integrity only.

Regression FAIL means a matching check changed PASS→FAIL. Missing checks, UNKNOWN reports or different kinds/profile fingerprints yield UNKNOWN. Otherwise PASS means no newly observed regression in the comparable checks, even if a pre-existing failure remains; read both reports. It is never automatic release approval.

Reports are single-owner, stored as private JSON for at most 24h and 128 reports, and have an individual size cap of 2 MiB. Railway storage is ephemeral; reports may disappear on restart/redeploy. Artifacts and browser outputs are temporary and removed after the call. There is no multi-tenant isolation or permanent evidence archive. Read the report into your own evidence store when needed.

Limits: 2 MiB decoded upload; 3 MiB HTTP body; 100 ZIP entries; 8 MiB total expansion; 2 MiB per expanded file; compression-ratio guard; duplicate/traversal/drive paths, encrypted entries, links and special files refused. Profile 64 KB, at most 12 scenarios × 40 steps. Worker deadlines 30s static/90s local browser, CPU/file descriptor/output limits and process-group cleanup. Remote service memory/CPU limits are also set at Railway. No upstream security-scanner or full DOM/CSS validator claim.

## Tests

```sh
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests -q
python scripts/selftest.py
# From repository root:
python -m unittest discover -s tests -v
node --test adapters/sites/tests/*.test.mjs
```

`evidence/` contains this change's executed evidence. Deployment, protocol calls, ChatGPT credential activation, mobile real-device tests and public release are separate acceptance states. See `docs/VERIFICATION.md` for actual results and remaining gaps.
