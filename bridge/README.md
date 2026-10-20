# ALDOL MCP Forge: Python write-tool bridge (development integration)

Status: **implemented as a trusted local worker + authenticated loopback HTTP gateway**. Not deployed, not integrated with a live Sites write tool, and not a v0.5 release.

## Why this exists

ChatGPT Sites' deployed JavaScript Worker cannot run the existing Python subprocess, namespace verifier, or archive generator. The existing three read-only tools continue to run in the owner-private Site unchanged.

The five tools requiring Python are implemented through the existing Forge core:

| Tool | Worker operation | Safety boundary |
|---|---|---|
| `forge_create` | `forge._create` | Verified project slug, exclusive create, quota 20 |
| `forge_add_tool` | `forge._add_tool` | Existing lock, manifest validation, backup |
| `forge_test` | `forge._test` | Original compatibility checks, official SDK when installed |
| `forge_package` | `forge._package` | Test-before-ZIP, no overwrite, checksum-only artifact ID |
| `forge_import_openapi` | `forge._import_openapi` | GET-only, dry-run default, no live API variables |

### Files

- `bridge/worker.py`: mandatory operator-controlled workspace root and **verified subject**, separate per-subject folders, strict allowlist and bounds, serialized calls, 20-project quota. Public JSON results do **not** expose local paths. This is a local worker process, not a network listener or sandbox.
- `bridge/gateway.py`: loopback-only `127.0.0.1:8765` JSON API, requires 32+-character secret, owner identity from fixed server config, rejects browser Origin and unknown top-level fields. Child process does not inherit the gateway secret. No CORS or public binding.
- `bridge/test_worker.py`, `bridge/test_gateway.py`: local real operation and HTTP tests using temporary directories.

### Local developer test

From the trusted Forge source checkout:

```sh
python -m unittest discover -s bridge -p 'test_*.py' -v
```

To verify generated projects through the **official** SDK as well, install `mcp==2.0.0` in a dedicated test environment first. GitHub Actions installs it for the bridge job.

### Optional private gateway startup

Only on a trusted host, with an already-created **absolute** workspace directory:

```sh
export FORGE_BRIDGE_WORKSPACE_ROOT=/ABSOLUTE/TRUSTED/forge-bridge
export FORGE_BRIDGE_OWNER_SUBJECT=verified-owner-identity
export FORGE_BRIDGE_SECRET='use-a-fresh-random-secret-of-at-least-32-characters'
python bridge/gateway.py
```

This only binds to loopback. **Do not expose port 8765 to the internet.** A future remote integration requires an authenticated HTTPS frontend with network restrictions, secret management and transport-level access controls. It must not be exposed via a public unprotected reverse proxy.

Example trusted request from the same host:

```sh
curl --fail-with-body \
  -H 'Content-Type: application/json' \
  -H "X-Forge-Bridge-Secret: ${FORGE_BRIDGE_SECRET}" \
  --data '{"tool":"forge_create","arguments":{"project_name":"sample-html","description":"HTML 게임 검사"}}' \
  http://127.0.0.1:8765/v1/execute
```

The `--subject` parameter is set by the gateway's operator-configured identity, **not** the caller's JSON. Current gateway supports **one owner only**; it does not claim multi-user Sites authorization. A real deployment must also bind the authenticated Site viewer identity and per-tool authorization to that identity, never trust a subject string supplied by the model.

## Current hard boundaries

- **No write tools exposed by ChatGPT Sites yet.** There is no Sites-side authenticated viewer-identity to Python bridge integration here.
- **No paid cloud host has been created or deployed.** Railway currently has no existing projects visible; Vercel has several existing projects but no verified persistent Python Forge service.
- **No private key or bearer token committed.** Never put keys in `.openai/hosting.json`, GitHub Actions logs or public source.
- **No public ZIP download endpoint.** Packaging returns `artifact_id` (SHA-256) and byte size only. Authorizing and streaming packages will require a separate server-side artifact handler and storage policy.
- **Not a general untrusted code sandbox.** Existing generated-code tests run only curated templates and parsed GET operations. A real exposed service needs process/container-level isolation, quotas, timeout, monitoring and outbound networking restrictions; basic workspace directory separation alone is not sufficient.
- **No network / arbitrary command tools added.** Live API environment variables are unset for the Python subprocess; `forge_import_openapi` remains dry-run by default.
- **No execution on Sites host.** Existing owner-private read-only Site is untouched.
- **No behavior change to v0.3.2's Forge**. The whole integration is opt-in.

## Remaining work before Site write tools

1. Confirm the actual Sites authenticated viewer-identity propagation contract and per-tool write approval model. Do not infer identity from untrusted request fields or headers supplied by the browser.
2. Identify a trusted persistent Python host and deploy a hardened endpoint with HTTPS, secret rotation, monitoring and isolation. Prefer an existing host; do not provision paid resources without consent.
3. Implement a Sites-side authenticated service-to-service client using **server-side credentials** and a server-derived identity. Keep write tools absent from `tools/list` unless all dependencies exist.
4. Add a server-side artifact download API with authorized owner and SHA validation, or R2 storage with verified permissions and expiry.
5. Verify actual ChatGPT `tools/call` with a **test project only**, write consent, isolation and regression checks. The current three read-only Site tools must remain unchanged until this passes.
