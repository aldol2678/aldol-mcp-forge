# ALDOL Game Ops | Open-source QA toolkit

A platform-agnostic game QA workflow with a real local HTML/ZIP static and optional browser test runner. This folder is independent of the parent MCP Forge runtime and can be extracted into its own repository.

## Status

- **Recovered source:** ALDOL Game Ops personal plugin release v0.3.0 (2026-10-19), 12 original files preserved in this directory.
- **What runs today:** local Python CLI with static inspection, ZIP resource resolution, optional Node syntax checking, optional Playwright/Chromium responsive checks, declarative gameplay scenarios, and same-profile regression comparison.
- **MCP status:** **This is not yet a standalone MCP server.** The existing ChatGPT plugin packages skills and the local runner, not an executable MCP tool. MCP SDK adapter and remote deployment are future work, not claimed as completed.
- **Hosting:** no service, remote API, game deployment, CI/CD connection, or automatic publishing is performed by the QA runner.

## Quick start

Python 3.10+ required. Node.js is optional for JavaScript syntax diagnostics. Playwright Python and a Chromium executable are optional for responsive and scenario QA.

```sh
python scripts/selftest.py
python scripts/html_qa.py examples/demo.html --output ./qa-output
python scripts/html_qa.py examples/demo.html --profile profiles/regression-smoke.json --output ./qa-output-demo
python scripts/html_qa.py candidate.html --baseline previous.html --output ./qa-diff
```

For optional local browser tests in a restricted environment, install Playwright and Chromium independently. Set `ALDOL_CHROMIUM` to your Chromium path. If unavailable, browser checks are **UNKNOWN**, not PASS.

## What the runner checks

1. HTML/ZIP entry point, bundled assets, simple JavaScript syntax, and SHA-256 evidence.
2. Desktop/mobile-viewport **browser emulation** when dependencies exist. Layout overflow, minimum touch sizes, JavaScript exceptions, screenshots and configured tabs.
3. JSON scenario actions and assertions for a particular game. The Jelly Lab sample profile is game-specific; do not apply its expected state to unrelated games.
4. Previous/candidate artifact comparison on matching test IDs. `NO_REGRESSION_DETECTED` means no regression **within compared tests**, not a global game-quality guarantee.

## Usage and safety boundaries

Do not run untrusted HTML directly on your everyday device or privileged CI runner. The browser stage executes user-supplied JavaScript. Browser request-abort routing is not an isolation boundary (it does not address all exfiltration paths). Run browser QA as an unprivileged separate OS/container environment with outbound networking disabled and no credentials. No local script is a remote sandbox by itself.

Browser loads use `page.set_content` with simulated localStorage, not the real deployed origin. Real Android/iOS physical devices, GPU/game-engine performance, live multiplayer, Production and persistence across real reloads are **NOT verified** by this runner.

Test input files are left unmodified. JSON/screenshots are written under `--output`. Never treat an exit status of 0 as evidence that UNKNOWN checks passed. Check `candidate/report.json`, `summary.json`, and `regression.json` when applicable.

## Open-source scope

MIT-licensed game QA runner, project-agnostic skills, bundled sample profiles and tests. The original private ChatGPT plugin's installation, permissions, backend ID, and release are not made public or changed by publishing this source. There are no bundled proprietary game source files, user secrets or customer datasets.

Source provenance: private plugin `aldol-game-ops` release `pluginrel_6ad6150fdf6081918e38d771417d5b7d` (v0.3.0), recovered 2026-10-21. Public fork initially packaged under `packages/game-ops/` in ALDOL MCP Forge.

See [SECURITY.md](SECURITY.md) and [LICENSE](LICENSE).
