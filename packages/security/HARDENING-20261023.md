# Secret Guardian v0.1 hardening — 2026-10-23

Scope: existing Draft [PR #33](https://github.com/aldol2678/aldol-mcp-forge/pull/33), branch `feat/security-secret-guardian-v01-20261023`, base `feat/aldol-security-mcp-v01-20261022`. The remote head was re-read before work and matched `8866723527c7179b3d7bcf12bbdb83717e434c45`. No production changes, account-wide inventory, real credentials, cloud secret access, key lifecycle actions or new endpoint/deployment are part of this change.

## Threat model and changes

The trusted operator configures the allowed workspace and owns the service token. Repository contents, metadata, subpaths and HTTP input are untrusted. Readers of reports must not learn raw key values, variable names, paths, aliases, owners or exception details. Local concurrent writers are considered for deterministic swap defenses, but this service is not an OS sandbox.

| Threat / previous behavior | Severity | Defense and evidence |
| --- | --- | --- |
| SHA-256 of short names/paths/aliases can be guessed offline and correlated across reports | Medium | Fresh 256-bit in-memory HMAC key per report; key never emitted/persisted. Regression compares repeated scans, old dictionary hashes and record/risk joins. |
| Manifest path-based read followed an earlier symlink/size check; dotenv leaf no-follow did not protect parent replacement or growth | High | Anchor every directory component; relative `open` with `O_NOFOLLOW`, regular single-link files only, nonblocking open, before/after dev/inode/mode/link/size/mtime/ctime checks. Deterministic regular-file, symlink, FIFO, directory swap, growing-file and unlink tests. |
| Huge/growing files, many entries/records or deep traversal | Medium | 64 KiB manifest, 128 KiB per dotenv (+ one overflow-detection byte); at most 40 attempted dotenv reads, 30k entries, 64 directory levels, 300 combined records, 300 returned risks. Excess/failed reads mark coverage incomplete. Streaming directory enumeration avoids building unbounded entry lists. |
| Metadata booleans accepted as schema integer, duplicate fields, invalid types/dates, nonstandard JSON constants/deep JSON | Medium | Exact schema integer and category types; duplicate-field/NaN rejection; bounded decoding; parser errors become incomplete without echo. Existing field allowlist, duplicate alias, dates and rotation policy rules retained. |
| Optional manifest disappears after detection | Medium | Only an absent initial directory entry is optional; later disappearance is an invalid/incomplete manifest. Regression injects unlink. |
| Missing metadata interpreted as a positive security verdict | Medium | Add per-record `unknown_metadata`, aggregate unknown count and unverified evidence label. Existing status strings retained; no SAFE/PASS status introduced. Directory changes and read errors cannot yield complete coverage. |
| High-priority risk omitted behind low-priority rows when capped | Medium | Stable severity sort before risk truncation; truncation remains `FINDINGS_WITH_GAPS`. Counts describe returned risks, not undisplayed total. |
| HTTP non-ASCII auth caused compare exception; duplicate framing / malformed JSON / internal error leakage | Medium | Byte comparison, duplicate auth/framing rejection, strict JSON, 2 KiB request cap, 10s read timeout, static errors, existing single-scan semaphore. Loopback tests exercise malformed types/encoding, duplicate headers, timeout, concurrent scans, sanitized failure and recovery. |
| Shared scanner path preflight silently ignored traversal errors and resolved symlink subpaths | Medium | Traversal errors now block; symlink components rejected even within allowed root. Trivy/OSV/Syft commands, parsers and output contracts unchanged. |
| Mobile duplicate actions or uncertainty shown as success | Low | Explicit disabled-handler guard; 401 authentication message distinct from network failure; uncertain states include “not a safety verdict”; inventory disclaimer. Four real Chromium/loopback viewport tests. |

No defense here claims protection against privileged mount manipulation or an adversary controlling the service process. Directory identity/change checks improve detection; a mutable filesystem is not an atomic snapshot. Use a credential-free worker, immutable/read-only source mount, restricted filesystem and network access, and resource quotas as already documented.

## Identifier decision and migration

Options considered:

| Option | Privacy / tracking tradeoff |
| --- | --- |
| Unkeyed hash or published per-report salt | Offline name dictionaries remain possible; stable hashes additionally enable correlation. |
| Persistent HMAC key | Prevents offline guesses without the key and retains longitudinal correlation, but introduces key storage, rotation, distribution and compromise scope. Not justified for this local inventory version. |
| Process-scoped HMAC key | No persistent secret but links reports during process lifetime and changes identity on restart; awkward multi-worker semantics. |
| Fresh report-scoped HMAC key (selected) | No persistent secret or cross-report dictionary/correlation; stable references only within a response. Loses longitudinal tracking. |

`credential_ref` preserves its prefix and 16 lowercase hexadecimal characters. HMAC-SHA256 includes a source-domain prefix and uses a random 32-byte key, discarded after the report. The 64-bit suffix preserves format compatibility; with <=300 records, accidental collision probability is approximately 2.4e-15 per report. This is an opaque display reference, not an authentication token or durable database identity.

The response adds `reference_scope: "report"` and `reference_scheme: "hmac-sha256-64-v1"`. Consumers must stop joining refs across reports and keep each report's record/risk associations together. No persistent mapping from old hashes is provided; no saved state exists in this service to migrate. Strict consumers that reject additional JSON properties must update their validators for the additive fields. Module version remains 0.1.0; the new scheme field identifies the pre-release semantic change.

## Risk rule semantics and priority

All existing codes remain unchanged. Severity is operational review priority, not proof of exploitation. The highest severity is returned first when results are capped.

| Code | Severity | Exact basis |
| --- | --- | --- |
| USER_REPORTED_EXPOSURE | CRITICAL | Operator metadata says `suspected` or `confirmed`; both require urgent review, neither is externally verified. The code and `metadata_assurance` explicitly identify the source. |
| EXPIRED_BY_METADATA | HIGH | Supplied expiry is <= today's UTC date. Missing expiry is unknown, not expired and not confirmed valid. Date-only expiry is interpreted as the start of that date. |
| DOTENV_WORLD_READABLE | HIGH | Successfully inspected file has POSIX other-read bit set. This is permission exposure, not proof anyone read it; ACLs are not assessed. |
| ROTATION_OVERDUE_BY_METADATA | MEDIUM | Both rotation date and integer 1–3650 day policy are known and elapsed UTC days **exceed** the policy. Exactly on the limit is not overdue. Future rotation dates invalidate the manifest. |
| BROAD_PRIVILEGE_REVIEW | MEDIUM | Supplied privilege is admin/owner/root. Unknown privilege is not assumed narrow. |
| ROTATION_DATE_UNKNOWN | LOW | No rotation date supplied. |
| OWNER_UNKNOWN | LOW | No owner supplied; owner values are never returned. |

Provider inference from dotenv names is a heuristic, and metadata facts are unverified user input. Names/filenames never generate an exposure code. Metadata and dotenv inventories are separate, unlinked sources and can describe the same credential twice. The name parser recognizes a limited ASCII assignment syntax; it does not parse/evaluate complete shell or multiline dotenv grammar. Counts are inventory candidates, not proof of distinct/live credentials.

## Status and coverage interpretation

- Invalid/out-of-scope subpath or detected symlink: `BLOCKED`.
- Inspection failure, unsupported safe-file primitives or a limit with no returned risks: `INCOMPLETE`.
- Risks plus any inspection gap/truncation: `FINDINGS_WITH_GAPS`.
- Risks without an inspection gap: `FINDINGS` (evidence still local and unverified).
- Records without returned risks: `INVENTORIED`, potentially with unknown metadata. Never a safe verdict.
- No inventory and no read failure: `UNKNOWN`, even if an optional empty manifest is schema-valid.

`metadata_valid=true` describes schema validity only. `complete_within_local_scope` describes bounded inspection, not sufficient metadata or account-wide coverage. `dotenv_files_scanned` now counts successfully read files, not merely discovered candidates; failed reads still invalidate completeness. At most 40 read attempts occur. Directories in the existing skip set are not inventoried, but are traversed within the safety budget to preserve the no-symlink policy. Hardlinks and dotenv-shaped directories are refused/incomplete. File access can update OS access times on a writable mount; byte/mode/mtime/name invariance is tested, and strict metadata immutability requires a read-only mount.

## Validation and reproducibility

All target fixtures are temporary and synthetic. No workspace contents are transmitted externally by tests; browser requests are loopback only. Dependency installation downloads packages/browsers before testing. No raw HTTP traces or credentials are saved.

| Check | Result | Evidence / limitation |
| --- | --- | --- |
| Compile | PASS | `python -m compileall -q packages/security` |
| Security unit + loopback integration | PASS | 59 tests: original 30 preserved; deterministic race/input/rule/status/redaction/readonly/concurrency/legacy dispatch tests added. `security-unit.log` CI artifact. |
| Official Python MCP 2.0.0 | PASS | 6-tool discovery plus actual Guardian structured calls in memory and stdio: normal, blocked path, malformed manifest, all content/structured fields redacted, unchanged files. `security-sdk.log`. |
| Chromium browser | PASS | Pinned Playwright 1.56.0 Chromium; 360×800, 390×844, 412×915, 667×375: no horizontal overflow, >=48px controls, real authenticated loopback POST, duplicate prevention, 401/network distinctions, all gap statuses, empty local/session storage/cookies, no external requests. `security-browser.log`. Also checked the preinstalled Chromium 154 locally. |
| Existing Forge root suite | PASS | 26/26 in a clean SDK-free venv, matching the existing offline CI job. An initial run in the SDK-enabled venv hit three pre-existing expectation mismatches (test expects SDK absent); no unrelated code changed. |
| Trivy / OSV / Syft adapters | PASS | Existing unit tests retained, additional real HTTP dispatch/aggregation with mocked executable outputs. Actual binaries/databases were not installed or executed: **NOT_VERIFIED**, no production scan or external OSV lookup. |
| Android physical | BLOCKED | No physical Android device available; browser emulation is not a device result. |
| Remote protected QA authenticated POST | BLOCKED | Existing deployment metadata checked; no authorized QA bearer credential/device session provided or retrieved. No bypass, new share link or deployment. |
| GitHub required source-smoke CI | Pending readback at commit creation | Exact final commit/run URL and conclusion are recorded in PR #33 after the branch update. Local results alone are not reported as CI success. |

Reproduce with the README commands. The existing source-smoke workflow now includes the browser verifier in the same job, with a six-minute timeout and 14-day sanitized log artifact; no new workflow, schedule or deploy step. GitHub verifies its PR merge ref; final readback must confirm the run's `head_sha` matches the work-branch commit. Root Forge offline tests remain a separate SDK-free command; the MCP verifier is the SDK-dependent test.

## Existing remote environments (read-only metadata inspection)

- Independent QA: project `aldol-secret-guardian-qa`, deployment `dpl_HjTwRp7TBCE4pPMxdqSuCdzNKYHq`, READY, source `8866723527c7179b3d7bcf12bbdb83717e434c45`, URL https://aldol-secret-guardian-qa.vercel.app/. Vercel labels it **production of the separate QA project**; it is not Security production and does not contain this hardening update.
- Original service: `aldol-security-mcp`, deployment `dpl_E3N2X7WwkCQrgPcMok62xFrzXg14`, READY, source `4246e6f7a664145a3f7b48a7ad4858022e99ddd2`, URL https://aldol-security-mcp.vercel.app/. Only deployment metadata was read; the service was not scanned or changed.
- No deployment, environment-variable edit, token retrieval, permission expansion, merge or main-branch change was performed. Final PR status and deployment aliases are re-read after pushing the work branch.

## Residual risks and follow-up

| Risk / severity | Evidence and reproducibility | Impact / recommended follow-up |
| --- | --- | --- |
| Mutable tree / privileged mount adversary — High if deployed on untrusted shared writable mounts | Deterministic file/directory swaps fail closed; arbitrary concurrent mutation is not exhaustively provable. An open inode can be renamed outside its original tree; privileged mounts/hardlink unlink races are outside application isolation. | Do not rely on Python preflight as a sandbox. Enforce immutable source mounts and credential-free OS isolation before using hostile workspaces. External scanners still consume paths after preflight. |
| Private HTTP availability — Medium | Scan semaphore and 2 KiB/10s limits tested; stdlib threaded HTTP server has no global connection/thread quota and is not a public auth service. | Keep behind existing private TLS/auth proxy; use proxy rate/connection limits and worker quotas before broader use. No exposure expansion in this PR. |
| Local-only heuristic inventory / unverified metadata — Medium | Missing fields and empty input explicitly represented; parser does not interpret full dotenv syntax or verify cloud permissions/expiry. Reproduce with missing metadata or multiline values. | Complete operator metadata and review findings manually. Do not infer account-wide coverage, breach proof or safety. Future grammar improvements require separate scope/tests. |
| Report-scoped identifiers — Low compatibility risk | Repeated reports intentionally differ; schema includes scheme/scope. | Update consumers that persisted old refs; use whole-report review. Stable pseudonyms would need a separately reviewed key lifecycle. |
| External binaries / vulnerability databases — Medium verification gap | Adapter regressions use controlled output; actual pinned binaries/database freshness not tested here. | Perform isolated, network-controlled binary acceptance tests before any runtime release; missing/stale DB must remain UNKNOWN. |
| Android and protected remote QA — Medium release-evidence gap | Emulation passes, but no physical device or authorized remote bearer POST. Existing QA stays on old source. | Owner performs device login/touch and an authorized synthetic POST in the existing protected QA environment after a separately authorized QA update. Keep Draft and do not equate code verification with release. |

## Changed files

| File | Purpose |
| --- | --- |
| `secret_guardian.py` | Per-report HMAC, metadata uncertainty, strict JSON, bounded fd traversal, honest coverage, priority truncation. |
| `guardian_io.py` (new) | No-follow anchored directory/file operations and bounded race-checked reads. |
| `engine.py` | Preserve scanner commands; block symlink subpaths and traversal errors; allow Guardian to apply its fd traversal. |
| `http_api.py` | Auth/framing/parser/timeouts and error sanitization while preserving routes and scan lock. |
| `mobile.js`, `mobile.html` | Duplicate guard, clear authentication/gap states and inventory disclaimer; existing layout retained. |
| `tests/test_guardian_hardening.py` (new) | Adversarial file/input/rule/status/privacy/readonly regressions. |
| `tests/test_engine.py`, `tests/test_http_integration.py` | Shared preflight regressions, real loopback auth/errors/concurrency and legacy scanner routing. |
| `tests/sdk_verify.py` | Real Guardian tool calls on official SDK in both transports. |
| `tests/mobile_http_client.mjs` | Match improved authentication label in existing real-fetch simulated DOM test. |
| `tests/browser_verify.py` (new), `requirements-test.txt` (new) | Reproducible four-viewport Chromium + loopback tests and pinned test dependency. |
| `README.md`, `HARDENING-20261023.md` | Current functionality/limits, threat review, migration and evidence. |
| `../../.github/workflows/security-source-smoke.yml` | Extend existing CI job with browser verification and sanitized log artifact. |
