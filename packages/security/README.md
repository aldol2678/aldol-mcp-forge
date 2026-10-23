# ALDOL SECURITY MCP v0.1.0

A source-available, read-only security orchestration service. Trivy scans filesystem vulnerabilities, misconfigurations, and secret matches; OSV-Scanner checks dependency vulnerabilities; Syft summarizes CycloneDX SBOM packages. **The external binaries are not bundled or installed by this repository.**

## Scope and current status

- This is **new source code** under packages/security; a code-review PR is not a deployment.
- Python standard-library engine, official MCP Python SDK v2 stdio adapter, token-guarded localhost HTTP API, responsive browser dashboard.
- Six MCP tools: security_capabilities, security_scan_trivy, security_scan_osv, security_inventory_sbom, security_scan_all, security_secret_guardian.
- Allowed filesystem root must be explicitly configured. Arbitrary URLs, git cloning, writes to target files, remediation commands and remote code execution are not supported.
- No production scan or Android physical-device validation is implied by offline tests.
- Scanner databases must be locally prepared; no findings is never a security guarantee.

## Quick start (trusted workspace)

Requires Python 3.11+, and optionally installed Trivy, OSV-Scanner v2 and Syft binaries.

    cd packages/security
    python -m pip install -r requirements.txt
    export ALDOL_SECURITY_ROOT=/path/to/trusted/read-only/project
    python mcp_server.py

Example stdio client entrypoint: python /absolute/path/packages/security/mcp_server.py, with ALDOL_SECURITY_ROOT configured in its environment.

For a browser dashboard accessible from Android via a **private TLS reverse proxy**:

    export ALDOL_SECURITY_ROOT=/path/to/trusted/read-only/project
    export ALDOL_SECURITY_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
    python http_api.py

The HTTP API binds 127.0.0.1:8765 by default. Health is GET /health, authenticated capability check GET /api/capabilities, and authenticated scan POST /api/scan. Use Authorization: Bearer <server-token>, with JSON body such as {"tool":"all","subpath":"."}. The mobile UI is GET /.

IMPORTANT: The mobile HTTP service is **not** an MCP transport and **not** ChatGPT Android plugin connectivity. The SDK entrypoint is local stdio only. ChatGPT remote-app connectivity requires a separate authenticated Streamable HTTP/OAuth implementation and actual device testing. The dashboard operates on the server-mounted workspace, not on Android local files.

## Scanner commands

- Trivy: filesystem JSON, vulnerability/config/secret scanners, offline mode and all DB auto-updates disabled. Preseed the vulnerability DB under a controlled scanner cache; absent/stale DB can cause UNKNOWN. This release does not validate database freshness.
- OSV-Scanner v2: scan source --recursive --format json. **External dependency lookup is disabled by default.** To permit package metadata disclosure to OSV, set ALDOL_SECURITY_OSV_NETWORK=1 after reviewing the data-sharing implications.
- Syft: directory source to CycloneDX JSON (aggregate counts only). Raw SBOM data is not returned by MCP or HTTP.

Only sanitized counts and vulnerability identifiers are exposed. Secret values, matching snippets, raw stderr/stdout, absolute target paths and raw SBOMs are deliberately withheld. Scanner output is bounded to 12 MiB; filesystems with more than 30k entries, or symlinks, are refused. Scan processes have a timeout. No shell invocation is used.

## Known limitations and safety

- Scanner executables run on the host with the service account's OS privileges. This is not a sandbox. For untrusted repositories use a disposable, credential-free worker with a **read-only** source mount, no host Docker socket, CPU/memory quotas, and network blocked except optional OSV egress.
- Public internet exposure with a static bearer token is **not** recommended. The browser API is a private management surface, not a multi-tenant authentication system. Do not pass tokens in URLs or store them in browser storage.
- OSV schema or upstream CLI flags may change; update adapters after pinning/installing actual binary versions.
- Trivy cache updates may require a separate privileged maintenance job; scanner cache must not be located inside the project.
- Return states NO_FINDINGS_IN_SCOPE, FINDINGS, UNKNOWN, BLOCKED, INVENTORIED and INCOMPLETE are explicit; UNKNOWN, INCOMPLETE, FINDINGS_WITH_GAPS or BLOCKED must never be rendered as PASS. INVENTORIED is an inventory result, not a safety verdict.
- The path/symlink checks cannot guarantee isolation against a malicious co-tenant mutating the tree concurrently. Enforce immutable read-only mounts at OS level.
- HTTP dashboard requires TLS provided by your trusted reverse proxy. No server is automatically deployed or connected.

## Offline tests

    python -m unittest discover -s tests -v
    python -m compileall -q .

Offline unit tests verify path policy, secret redaction, status honesty, parser aggregation and command invocation patterns with mocks. They do **not** run actual Trivy, OSV or Syft binaries. The separate SDK verifier below performs official MCP SDK calls in memory and over stdio.

## License and upstream

MIT for this package (see LICENSE). Trivy, OSV-Scanner and Syft are external open-source projects with their own licenses and separate distribution requirements.


## Vercel protected preview deployment (container)

A Dockerfile.vercel is included for Vercel Container Functions. The image verifies the SHA-256 digests of pinned Trivy v0.76.0, Syft v1.54.1 and OSV-Scanner v2.6.0 binaries during build. This only demonstrates binary installation. Trivy vulnerability DB is not bundled (vulnerability checks may report UNKNOWN), and OSV outbound requests remain disabled. The mounted workspace is limited to the source files included in this image; no arbitrary GitHub repository scanning is available.

Create a separate Vercel team project linked to the repository, set the rootDirectory to packages/security and target only the reviewed feature branch, enable Vercel Authentication for all deployments and inject ALDOL_SECURITY_TOKEN as a sensitive preview secret (never commit tokens). The container listens on PORT and binds 0.0.0.0, with Vercel's HTTPS edge in front.

Do not claim official MCP remote transport or permissioned repository scanning from the web UI. Any future remote MCP endpoint requires dedicated OAuth authorization, tenant-scoped repositories and execution isolation.


## Secret Guardian v0.1 (2026-10-23)

Read-only workspace inventory using local .env variable NAMES and an optional operator-managed secret-guardian.inventory.json metadata file. It does not inventory or output key values, fetch cloud secrets, auto-rotate credentials, or prove that a key leaked. External repository/account coverage is not supported by v0.1.

MCP tool: security_secret_guardian(subpath="."). Authenticated HTTP: POST /api/scan with {"tool":"guardian","subpath":"."}. The existing Android-friendly browser selector also offers Secret Guardian; this is not remote ChatGPT MCP transport.

Example metadata ONLY (never include actual keys):

    {"schema_version":1,"credentials":[{"ref":"openai-prod-1","provider":"openai","environment":"production","privilege":"write","owner":"engineering","last_rotated_at":"2026-10-01","expires_at":"2027-01-01","rotation_policy_days":90,"exposure_status":"unknown"}]}

Allowed provider categories: github, vercel, supabase, gcp, openai, railway, other. Inputs are allowlisted, and fields containing secret/key/value content are rejected. Risk codes include USER_REPORTED_EXPOSURE (based ONLY on supplied metadata), EXPIRED_BY_METADATA, ROTATION_OVERDUE_BY_METADATA, BROAD_PRIVILEGE_REVIEW, ROTATION_DATE_UNKNOWN, OWNER_UNKNOWN, and DOTENV_WORLD_READABLE. Key names, relative paths and aliases are represented by report-scoped HMAC references. References intentionally change on every call; see the compatibility notes below. Never consider UNKNOWN/INCOMPLETE/BLOCKED safe. No scheduled job is installed. Use existing read-only mounts and access-token protections.

Offline checks: python -m unittest discover -s tests -v

Additional guardrails: descriptor-relative no-follow reads, before/after file identity and mutation checks, bounded bytes/entries/depth, single-link regular files, strict JSON metadata validation, and incomplete coverage on read failures. Dotenv bytes necessarily pass through a bounded memory buffer while extracting names; values are never retained in records, hashed, returned, logged or persisted. No dotenv expressions are evaluated.


## Isolated HTTP + simulated mobile-client integration checks

CI runs a real loopback-only HTTP server (`127.0.0.1:0`) with a disposable temporary workspace and **synthetic test-only values**, then exercises:
- HTTP bearer authentication, invalid payload rejection, existing OSV block behavior, health and capability responses.
- Secret Guardian JSON redaction, path safety, and unchanged bytes in the allowed workspace.
- HTTP serving of the mobile HTML/JavaScript and the unchanged UI client's button-click code run through Node's simulated DOM, making real loopback HTTP requests and testing success/401/missing-token paths.

Run locally with Python 3.11+ and Node.js 22+:

```sh
python -m unittest discover -s packages/security/tests -v
```

These tests never call cloud providers and do not expose HTTP to the public internet. Simulated DOM verification does **not** verify real Android browser layout, touch handling, protected Vercel preview, remote MCP/OAuth integration, or external API key inventory. A private, explicitly authorized device test is still needed before claiming those capabilities.


## Guardian hardening and reproducible verification

See [the threat model, risk rules, compatibility changes and verification report](HARDENING-20261023.md).

- `credential_ref` retains `env-`/`meta-` plus 16 hex characters, but **is now valid only within one report**. Do not join or cache credentials across scans by this value. There is no persistent HMAC key, old-to-new mapping or automatic migration. New `reference_scope` and `reference_scheme` fields identify this behavior.
- Existing statuses and risk codes are preserved. Additive `unknown_metadata`, `metadata_assurance` and `unknown_metadata_records` make missing facts and self-reported evidence explicit. `metadata_valid=true` means schema-valid, not independently verified. Missing expiry does not imply expired or unexpired. `complete_within_local_scope=true` means bounded local inspection completed, not complete account coverage or security assurance.
- POSIX descriptor/no-follow support is required for Guardian; unsupported platforms fail closed. Hardlinked dotenv/manifest files are refused. Scanner invocation contracts remain unchanged; their path preflight now also refuses symlink subpaths and traversal errors.
- HTTP scans require `Content-Type: application/json`, one `Content-Length`, and one Bearer header. Duplicate JSON keys, nonstandard constants, ambiguous framing and incomplete bodies are rejected. Existing JSON clients remain compatible. Scan concurrency remains one; incomplete requests time out after 10 seconds.

From the repository root in a dedicated Python 3.11+ virtual environment:

```sh
python -m pip install -r packages/security/requirements-test.txt
python -m compileall -q packages/security
python -m unittest discover -s packages/security/tests -v
python packages/security/tests/sdk_verify.py
python -m playwright install --with-deps chromium
python packages/security/tests/browser_verify.py
```

The browser verifier uses the pinned Playwright Chromium against a real temporary `127.0.0.1` server at 360×800, 390×844, 412×915 and 667×375. It tests layout, touch sizes, duplicate execution, authentication vs connection failure, uncertain states, and empty browser storage. It does not bypass CSP or contact a remote deployment. `ALDOL_TEST_CHROMIUM` may explicitly select a local Chromium; CI uses the pinned browser. Optional `ALDOL_TEST_BROWSER_OUTPUT` saves screenshots only after clearing the synthetic token field.

The existing source-smoke workflow runs these checks and retains sanitized summary logs for 14 days. The unrelated root `tests/` suite expects an environment **without** the MCP SDK, matching its existing CI offline job; run it in a separate clean environment. Android physical-device and protected remote bearer-authentication tests remain unverified. The existing `aldol-secret-guardian-qa` deployment is independent of `aldol-security-mcp` production and is not updated by these instructions.
