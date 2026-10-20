# ALDOL MCP Forge Studio: official SDK job integration

**Development status (2026-10-20):** SDK button, signed remote-job protocol, localhost Python execution service and CI are implemented. **Production integration NOT active.** Existing owner-private Sites v5 and R2 objects have not been changed by this PR.

## User experience after a real private SDK host is configured

In Forge Studio > **검증실**, select a saved project and click **공식 SDK 실행 검증**. The Site generates the project's immutable ZIP, compares its source-file checksums, then sends it to an operator-approved Python SDK service over authenticated HTTPS. The status is refreshed periodically and recoverable after reload through an owner-scoped R2 job pointer. The UI only shows SDK PASS if the Python service returns a verified official SDK **in-memory and stdio** PASS with zero live API calls. In every other case it displays UNKNOWN/FAIL/SKIP, never simulated success.

Before hosting is configured, the button stays disabled and the Site explicitly shows SDK **SKIP**. Existing `forge_test` continues to be file-integrity only and cannot falsely report Python execution success.

## Security boundary

- Current Sites authenticated user ID is read from `oai-authenticated-user-id` at the trusted Sites dispatch boundary. It is **never** read from a form, URL, project metadata or model tool arguments.
- The Site computes a SHA-256 subject scope and signs the exact server-to-server JSON body with HMAC-SHA256 using its **private backend secret**, current timestamp, and fixed path.
- The Python listener `bridge/sdk_job_gateway.py` binds **127.0.0.1:8775 only**. It rejects unsigned, expired, oversized, cross-user or unsupported requests. A production HTTPS proxy must preserve the signed request bytes and must have network-level access control. Never expose the raw listener or open a public unauthenticated endpoint.
- Each job is content-addressed by viewer scope + project UUID + ZIP SHA-256, so retries never silently create extra evaluations. The worker enforces request-size, ZIP-size, capacity and subprocess timeout limits. ZIPs are removed after completion.
- Before Python import, `ci/verify_studio_archive.py` validates ZIP member allowlists, sizes, CRC, SHA256SUMS **and exact generator source parity**. Even a fully recomputed attacker-supplied hash list is insufficient to authorize arbitrary Python.
- **This is not a general-purpose sandbox.** Verifier execution needs an operator-controlled OS/container isolation boundary, outbound-network policy, disk quotas and monitoring before enabling service for wider/hostile use. The current use case is approved Forge-generated code, not arbitrary source uploads.

## How to test locally

From this repository, in a trusted Python + Node development runner:

```sh
node ci/generate_studio_sdk_fixtures.mjs
python -m pip install "mcp==2.0.0"
python -m unittest bridge.test_sdk_job_gateway -v
cd adapters/sites
node --test tests/*.test.mjs
bash scripts/build.sh
node scripts/validate-artifact.mjs
```

The first two commands prepare real Sites-generated curated/OpenAPI ZIPs and SDK dependencies. The bridge integration test starts a localhost HTTP server with test-only signing credentials, submits ZIPs, polls status and confirms actual SDK execution and cross-owner rejection. It does not deploy a service.

## Proposed private host configuration, only after an operator chooses one

1. Choose a **trusted, persistent** Python 3.12 host with an installed `mcp==2.0.0` test environment. Reuse an existing machine when possible. Do not start new paid infrastructure without approval.
2. Create a fresh private `FORGE_SDK_WORKSPACE_ROOT` as an absolute existing directory and store `FORGE_SDK_BRIDGE_SECRET` (32+ random characters) in the host's secret manager.
3. Start `python bridge/sdk_job_gateway.py` with those environment variables. It listens only on loopback; configure a vetted HTTPS proxy or authenticated tunnel **without** opening port 8775 publicly.
4. In the **existing owner-private Sites project**, configure these server-side secrets/bindings, not source files:
   - `SDK_BRIDGE_ENABLED=1` (enable **last**, after E2E validation)
   - `SDK_BRIDGE_URL=https://<trusted-private-endpoint>/v1/sdk/jobs`
   - `SDK_BRIDGE_ORIGIN=https://<trusted-private-endpoint>`
   - `SDK_BRIDGE_SECRET=<matching protected secret>`
   - Existing `BUCKET` (R2) and `FORGE_WRITES_VERIFIED=1` must remain bound and verified
5. Confirm request signing, forged user denial, nonexistent project denial, timeout/retry behavior, private ZIP handling, and official SDK in-memory/stdio responses in the **actual Sites authenticated-user flow** before enabling the button.
6. Refresh the existing Forge Studio deployment from the correct GitHub commit and verify Site version/source matches it. Do not copy this code to a second Site or widen owner-private access.

## CI and review

- New workflow: `.github/workflows/verify-studio-sdk-jobs.yml`.
- Existing PR #7 provides strict ZIP gate and SDK v2 runner; this is a **stacked PR based on PR #7**, not an independent feature branch from main.
- Original Python Forge generation, original eight ChatGPT MCP tools, existing R2 project records, and public/production deployment policies remain unchanged.
- No secret values or user artifacts are committed or uploaded to a public GitHub Actions artifact.

**Explicitly not completed by this PR:** connecting/deploying an HTTPS Python host, configuring Sites secrets, modifying live Sites v5, proving user-specific SDK execution in production, merging either PR, or releasing v0.5.
