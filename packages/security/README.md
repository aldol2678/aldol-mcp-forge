# ALDOL SECURITY MCP v0.1.0

A source-available, read-only security orchestration service. Trivy scans filesystem vulnerabilities, misconfigurations, and secret matches; OSV-Scanner checks dependency vulnerabilities; Syft summarizes CycloneDX SBOM packages. **The external binaries are not bundled or installed by this repository.**

## Scope and current status

- This is **new source code** under packages/security; a code-review PR is not a deployment.
- Python standard-library engine, official MCP Python SDK v2 stdio adapter, token-guarded localhost HTTP API, responsive browser dashboard.
- Five MCP tools: security_capabilities, security_scan_trivy, security_scan_osv, security_inventory_sbom, security_scan_all.
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
- Return states NO_FINDINGS_IN_SCOPE, FINDINGS, UNKNOWN, BLOCKED, INVENTORIED and INCOMPLETE are explicit; UNKNOWN or BLOCKED must never be rendered as PASS.
- The path/symlink checks cannot guarantee isolation against a malicious co-tenant mutating the tree concurrently. Enforce immutable read-only mounts at OS level.
- HTTP dashboard requires TLS provided by your trusted reverse proxy. No server is automatically deployed or connected.

## Offline tests

    python -m unittest discover -s tests -v
    python -m compileall -q .

Offline unit tests verify path policy, secret redaction, status honesty, parser aggregation and command invocation patterns with mocks. They do **not** run actual Trivy, OSV, Syft or the official MCP SDK handshake.

## License and upstream

MIT for this package (see LICENSE). Trivy, OSV-Scanner and Syft are external open-source projects with their own licenses and separate distribution requirements.


## Vercel protected preview deployment (container)

A Dockerfile.vercel is included for Vercel Container Functions. The image verifies the SHA-256 digests of pinned Trivy v0.76.0, Syft v1.54.1 and OSV-Scanner v2.6.0 binaries during build. This only demonstrates binary installation. Trivy vulnerability DB is not bundled (vulnerability checks may report UNKNOWN), and OSV outbound requests remain disabled. The mounted workspace is limited to the source files included in this image; no arbitrary GitHub repository scanning is available.

Create a separate Vercel team project linked to the repository, set the rootDirectory to packages/security and target only the reviewed feature branch, enable Vercel Authentication for all deployments and inject ALDOL_SECURITY_TOKEN as a sensitive preview secret (never commit tokens). The container listens on PORT and binds 0.0.0.0, with Vercel's HTTPS edge in front.

Do not claim official MCP remote transport or permissioned repository scanning from the web UI. Any future remote MCP endpoint requires dedicated OAuth authorization, tenant-scoped repositories and execution isolation.
