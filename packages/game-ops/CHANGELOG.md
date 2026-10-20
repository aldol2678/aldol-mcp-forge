# Changelog

## 0.2.0 - 2026-10-19
- Removed GitHub/PR/CI as default assumptions. GitHub is one optional delivery route.
- Added game-by-game environment detection and source/version authority checks.
- Generalized release and QA paths for local HTML, platform-hosted games, Unity/PC builds and web/3D multiplayer.
- Updated AI handoffs to permit artifact URLs, platform versions and packaged builds instead of requiring a PR.

## 0.1.0 - 2026-10-19
- First private ALDOL Game Ops plugin.
- Added read-first release gate, webgame QA, and agent handoff workflows.

## 0.3.0 - 2026-10-19
- Added local `scripts/html_qa.py` for HTML/ZIP static inspection, Node.js syntax diagnostics, artifact SHA-256 and direct relative asset resolution.
- Added Playwright/Chromium responsive smoke checks, screenshot collection, page-error detection and configurable touch targets.
- Added declarative game profiles with Jelly Lab v0.4 scenario coverage (breeding, reward, menus, emulated storage).
- Added baseline/candidate same-profile regression comparison with scoped PASS/FAIL/UNKNOWN, missing tests and version hashes.
- Explicit separation of plugin skill packaging from a separately provisioned execution runtime; no MCP server, new external permissions, user game mutation or deployment.

## 0.4.0

- Six official Python MCP SDK tools; stdio and owner-authenticated Streamable HTTP.
- Bounded HTML/ZIP ingestion, optional SHA verification, private QA report IDs and conservative regression comparison.
- Default-denied browser/scenario execution, with local trusted-operator opt-in only; HTTP always blocks HTML execution.
- Docker/Railway deployment configuration, connection examples and protocol/security tests; original v0.3 CLI retained.
