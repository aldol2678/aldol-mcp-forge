# Game Ops MCP v0.4 implementation plan

User specification: build and actually call a Python-SDK MCP layer over the recovered v0.3 CLI, keep MIT and Forge runtime unchanged; reuse PRIVATE plugin and Railway environment.

Architecture: isolated `server.py` (MCP and authenticated HTTP), `service.py` (bounded artifact ingestion, reports and regression), `worker.py` (existing QA engine subprocess). Six requested tools retained. HTTP refuses all host paths and all browser execution; stdio confines paths to an operator-selected root and requires explicit browser opt-in. Uploaded bytes are base64, never fetched by URL. Owner-only bearer authentication, constant-time validation and bounded HTTP bodies; no token in source/plugin.

Execution: native implementation in the current session, as requested; separate git branch. No additional approval required for authorized implementation, test, PR, deployment, or existing private plugin update. Merge deferred until review and complete acceptance evidence.

- [x] Test ingestion/rejection, static PASS/FAIL/UNKNOWN, persisted reports and conservative regression before implementing service.
- [x] Implement subprocess runner with artifact/ZIP/profile limits, execution deadline and minimal environment.
- [x] Test official SDK stdio tools/list and tools/call, invalid inputs and normal EOF shutdown; implement six decorated tools.
- [x] Test authenticated HTTP (no/wrong token rejected, correct token calls; remote path/browser blocked), implement HTTP wrapper and deployment files.
- [x] Run original selftest, Forge Python + Sites tests, controlled own-fixture browser QA and new protocol tests.
- [x] Commit/push, open PR and inspect CI/changed files; deploy isolated Railway service and read back.
- [x] Update existing PRIVATE plugin only with verified endpoint/config; inspect source readback and actual host tools, distinguish pending auth/mobile.

Review focus: ZIP duplicates/traversal/links/bombs; symlink path escapes; missing/degraded regression checks and mismatched test profiles; timeout/worker failure must be UNKNOWN; reports and uploads bounded, private and transient. CLI browser route is a trusted-local execution facility, not an OS sandbox. Report limitation explicitly.

Acceptance distinction: implementation/stdio/authenticated HTTPS/PR/CI/private plugin saved and read back. Local browser UNKNOWN (Chromium absent); ChatGPT credential activation and actual Android invocation UNKNOWN. These blocked acceptance items are not marked completed by the implementation checklist.
