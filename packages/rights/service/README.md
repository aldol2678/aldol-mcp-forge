# ALDOL RIGHTS service v0.2.0

A single FastAPI application for the mobile web and remote MCP. Uses the original Python v0.1 engine through `policy.py`; existing SQLite functions and five stdio tools remain unchanged. The remote surface is intentionally read-only: six tools (`inspect_license`, `list_assets`, `check_usage`, `generate_credits`, `rights_report`, `review_history`). MCP checks compute without writing; web checks save snapshots and history.

## Run

Python 3.12; `pip install -r ../requirements.txt`; from `packages/rights`, run `RIGHTS_DEV=1 uvicorn app:app --port 8012`. Set `RIGHTS_DEV` **only** on localhost; production cookies are HttpOnly, Secure and SameSite Strict. `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` are public configuration, with the deployed ARAM project's verified defaults. No service-role key is needed or supported. Vercel auto-detects FastAPI from `app.py`. Static Korean UI is served by that same app; no Node runtime or duplicate policy port.

Apply `sql/001_rights.sql` once to the selected Supabase database. It is additive; namespaced tables and a private 10 MiB bucket only. It does not alter shared authentication settings. Execute explicit privilege revocations **before** granting column-level UPDATE (Supabase can set broad default table privileges). No pre-existing SQLite user database was present in this checkout; no invented migration.

## Authentication

Website: Supabase Auth email/password; server verifies `/auth/v1/user` each request, refreshes with a rotating refresh cookie, and rejects anonymous users. All mutations need same-origin checks and a custom request header. Session credentials never enter localStorage. Supabase email confirmation/delivery is inherited from the existing project; RIGHTS does not change redirect or mail settings.

MCP: native ChatGPT API-key Bearer authentication, separate from web sessions. A user creates a revocable read-only connection key at the website. The random 48-byte key is displayed once; only SHA256 is saved, maximum expiry 90 days. Enter it only in the host's secure authentication field, never a chat message or plugin source. OAuth/DCR/CIMD are **not implemented or claimed**. Clients requiring OAuth only cannot authenticate to this version; use native API-key capable clients or the website.

`rights_mcp_read` is an intentionally exposed SECURITY DEFINER RPC for opaque-key authentication. It has fixed `identity`, `assets`, `checks` actions, exact owner predicates, expiry/revocation/resource/scope checks and no writes or file access. Its anonymous-executable advisor warning is an intentional, reviewed trust boundary, not an unprotected table. Table RLS is independent and still protects website access. No key lets an MCP caller write records or fetch Storage originals. Stored metadata is untrusted, not an instruction source. The public publishable key cannot authenticate users or bypass RLS.

## Policy

Four statuses: SUITABLE (조건상 적합), CONFLICT (조건 충돌), REVIEW (추가 검토 필요), UNKNOWN (미확인). Results include basis, conditions, missing fields, confidence, engine version, check time and immutable asset snapshot/revision. `legal_clearance` is always false. A recorded URL/file is not authenticated evidence. SA derivative compatibility, MIT notices, Apache notices/patents, GPL source/linkage, OFL rename/distribution and custom contracts remain manual review. GPL-3.0-only/or-later references are supported by the web service without changing legacy core accepted license IDs.

## Files and reports

Only whitelisted extensions/MIME plus magic signatures (or UTF-8/JSON validation); active HTML, SVG and executables rejected. Uploads <=10 MiB. Files are returned as attachments through authenticated owner checks, never signed/public URLs or inline execution. Large assets can be recorded by source URL; large-file streaming is deferred. Replaced files remain private and are not destructively removed in this version.

Reports freshly re-evaluate the current saved usage, include credits and review-needed assets, and download as Markdown/JSON. Human verification of full license notices and modification notes is still necessary. Reports never silently truncate above 500 assets; the service explicitly blocks full reports instead. History is labeled latest 100. Create/check requests use stable UUIDs for retries; edits use optimistic revision matching. Client input is retained on network failure; partial upload progress is shown.

## Verification

Pure tests: `pytest packages/rights/service/tests/test_policy.py packages/rights/service/tests/test_api.py`; legacy: `python -m unittest discover -s packages/rights/tests` and repository-wide `python -m unittest discover -s tests`.

`tests/live_verify.py` and `tests/live_mcp.py` run only against **explicitly provisioned synthetic fixture users** via a private `RIGHTS_QA_CREDENTIALS` JSON path. They never print passwords or keys. Do not point them at real user accounts. Browser/device tests must be separately labeled; an SDK test does not prove a ChatGPT or Android invocation.
