# ALDOL MCP Forge Studio: official Python SDK v2 export validation

This milestone adds a **real, local/CI execution validator** for Studio-exported ZIP
artifacts. It does not make ChatGPT Sites capable of running Python processes.

## Validation boundary

1. Generate a project using the *unchanged* Sites Worker
   (`adapters/sites/worker/generator.js`).
2. Package with the *unchanged* Sites Worker ZIP exporter
   (`adapters/sites/worker/store.js`).
3. Inspect ZIP members, sizes, encryption/symlinks, CRC and every line of
   `SHA256SUMS`. Ignore no extra member and extract no user-chosen paths.
4. Before any Python import, compare code **byte-for-byte** with the approved
   Python Forge generator using `forge._validated` or
   `forge._validated_openapi`. This blocks injected Python even if someone
   recalculates the manifest and SHA-256 file list.
5. Run existing `verify_sdk.py` using official Python `mcp==2.0.0`.
   Exercise both **in-memory Client(app)** and a child-process
   **stdio client**. In OpenAPI mode, every sample call must remain GET
   and `dry_run` with `network_called: false`.
6. Return machine-readable `official_sdk: PASS|FAIL` separate from checksum
   integrity status.

Tests exercise deliberate corruption, a re-hashed executable code mutation,
unexpected members, traversal names and oversize manifest input. CI archives
only sanitized JSON evidence; original code/ZIPs are never uploaded as build artifacts.

## How to run for a downloaded ZIP

On a *trusted Python host with an authorized copy* of this repository:

```sh
python -m pip install --no-input "mcp==2.0.0"
python ci/verify_studio_archive.py /ABSOLUTE/PATH/studio-export.zip
```

The verification runner is intentionally not a public upload endpoint. Do not
feed other people's or untrusted arbitrary Python projects to
`verify_sdk.py`; use `verify_studio_archive.py` to enforce generator parity
first. This is code-integrity gating, **not an OS/container sandbox**.

Automated reproduction from actual Worker source:

```sh
node ci/generate_studio_sdk_fixtures.mjs
python -m unittest ci.test_studio_archive -v
```

GitHub Actions: `.github/workflows/verify-studio-sdk-export.yml`.

## Status and limits

- Official Python SDK execution of fresh Studio-generated curated and
  OpenAPI GET projects is testable in GitHub Actions **without a new paid host**.
- This proves compatibility of the exporter and existing Python SDK.
  It does **not** prove the *previously downloaded, user-specific ZIP* has
  been executed unless that exact file is separately supplied to the validator.
- Deployed Sites `forge_test` must continue to show `official_sdk: SKIP` and
  `python_execution: SKIP` until an authenticated execution/result channel exists.
- No Sites deployment, external API calls, shared file permissions, GitHub main
  edits, merge or release are part of this branch.
- Owner-private access and R2 data remain unchanged. PR #5 is a separate
  draft bridge, not a prerequisite for GitHub Actions to run this ZIP verifier.

### Next integration boundary

Decide between an already-controlled persistent Python worker and a
permission-scoped job service. The Site must send a **server-verified** owner
identity and immutable artifact/hash; the worker must verify the exact files
before running official SDK tests. Return an authenticated job ID, hash,
timestamp and verification results. Do not mark the Site UI PASS merely because
a similar CI fixture passed.
