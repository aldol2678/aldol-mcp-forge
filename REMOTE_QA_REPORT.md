# Secret Guardian remote QA report — 2026-10-23 UTC

**Outcome: BLOCKED. Neither Remote QA Verified nor Android Verified is claimed.**

Runtime source remains `01a519a522637c7e09fcddcf0d48b8701e972e31`. This delivery changes only four Markdown reports. No application, scanner, deployment configuration, CI workflow or credential was changed. The documentation commit is not a newly deployed runtime version.

## What actually ran

- GitHub connector: PR/head/Draft/base and exact-source CI reads; later documentation-only update of the existing work branch and PR description.
- Vercel connector: project/deployment/file-tree metadata, existing QA Dockerfile, environment **metadata with decrypt=false**, aliases/domains, documentation search and an attempted event-history read.
- Python standard-library HTTPS client: four unauthenticated GETs against **the existing old QA deployment**, with redirects disabled. Response bodies, cookies, redirect query strings and authorization data were not saved.
- Local Git blob extraction and SHA-256 verification of six runtime files.
- Docker Engine 28.4.0 on the local Unix socket; a QA-only image built from a pinned Python 3.12 image. Runtime: UID 10001, read-only root, no mounts/host ports, network=none, all capabilities dropped, no-new-privileges, 128 MiB memory, 1 CPU, 64 PID limit.
- Python HTTP probe **inside that local container**, using only loopback and a fresh synthetic test token passed through process environment, never printed or persisted in a report. The container was removed after testing.
- Existing security unittest suite rerun locally: **59/59 PASS**.

No deployment/create/promote/rollback/alias mutation, environment/auth change, secret decryption, bypass-link fetch, cloud account scan or production HTTP scan was executed. No remote QA token was retrieved.

## Remote deployment and authentication results

| Requirement | Actual result |
| --- | --- |
| New protected Preview READY | BLOCKED — no create request submitted |
| New Deployment ID / unique URL | None |
| Running new-source provenance | BLOCKED — no new runtime |
| Existing QA | READY, `dpl_HjTwRp7TBCE4pPMxdqSuCdzNKYHq`, old source `8866723527c7179b3d7bcf12bbdb83717e434c45` |
| Preview target / existing-alias preservation | DEPLOYMENT_BLOCKED; controls could not be established before mutation; details in preflight |
| Authorized owner-session UI | AUTH_BLOCKED — no owner session available; bypass helper deliberately unused |
| Application Bearer missing/wrong/valid at remote edge | AUTH_BLOCKED — outer Vercel gate not passed; no application-auth result claimed |
| Remote Guardian POST / invariant / repeated refs | BLOCKED — no new endpoint and no authorized QA client credential |
| New-deployment security headers and runtime logs | NOT_VERIFIED |

[Preflight](REMOTE_QA_PREFLIGHT.md) records the team, projects, protection, environment scopes, source hashes and deployment decision.

### Safe HTTPS checks on the old QA only

Host: `aldol-secret-guardian-qa.vercel.app`. TLS certificate validation was enabled; redirects were not followed.

| GET path | HTTP | Redirect host / path (query omitted) | HSTS |
| --- | --- | --- | --- |
| `/health` | 302 | `vercel.com` / `/sso-api` | Present |
| `/` | 302 | `vercel.com` / `/sso-api` | Present |
| `/mobile.js` | 302 | `vercel.com` / `/sso-api` | Present |
| `/api/capabilities` | 302 | `vercel.com` / `/sso-api` | Present |

These are outer Vercel Authentication challenges, not application 401 errors. They demonstrate that these unauthenticated requests did not receive the app content. They do not prove authorized access, app headers, correct new code, or authenticated POST. No real credentials were sent.

## Additional local container evidence — not remote evidence

The six source hashes in the preflight were checked again inside the running container. The QA-only Dockerfile and fixtures are packaging additions, not modifications to those source files.

| Local test | Result |
| --- | --- |
| `/health`, `/`, `/mobile.js` | PASS — 200; no-store, nosniff and CSP headers |
| Missing / intentionally wrong Bearer | PASS — 401 |
| Authorized synthetic Guardian POST | PASS — structured FINDINGS |
| `reference_scope=report`, `hmac-sha256-64-v1` | PASS |
| Two reports have distinct refs; risks join records inside one report | PASS |
| Self-reported exposure / expiry / overdue rotation / broad privilege / world-read permission | PASS — expected CRITICAL/HIGH/MEDIUM priorities |
| Variables, synthetic values, aliases, paths and synthetic auth token absent from reports | PASS |
| `../` / malformed-metadata fixture / empty fixture | PASS — BLOCKED / INCOMPLETE / UNKNOWN |
| Bad JSON / >2 KiB JSON body | PASS — 400 / 413 |
| Bytes, modes, filenames and mtimes before/after | PASS — identical in read-only container |
| Trivy/OSV/Syft installation | Absent, as intended; not scanner execution verification |
| External network | Disabled; only container loopback used |
| Race/concurrency/exception recovery | Existing 59-test local suite PASS; not destructively exercised on any remote filesystem |

Machine-readable local summary:

```json
{"source_sha":"01a519a522637c7e09fcddcf0d48b8701e972e31","passed":true,"source_files_verified":6,"http_auth":"PASS","hmac_contract":"PASS","risk_rules":"PASS","negative_requests":"PASS","workspace_invariant":"PASS","external_scanners_installed":false,"network":"container-loopback-only","remote_qa_verified":false,"android_physical_verified":false}
```

Local evidence directory: `/workspace/remote-qa-evidence/` contains `source-provenance.json`, `bundle-manifest.json`, `container-result.json`, `unauthenticated-https.json`, `local-security.log`, and allowlisted preservation snapshots. No tokens, cookies or bypass fields are included in those saved evidence files. The local `bundle/` contains only exact source and synthetic QA fixtures. It has not been uploaded to Vercel.

## Reproduction without credentials or deployment

From the repository root, extract each file listed in preflight with `git show 01a519a522637c7e09fcddcf0d48b8701e972e31:packages/security/FILE` into a new temporary build context; compare SHA-256 with the table. Do not copy an operator workspace or actual environment files. Add only synthetic fixtures as described below.

QA-only Dockerfile used:

```dockerfile
# QA-only, exact source; no scanner binaries, cloud SDKs or credentials.
FROM python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70
WORKDIR /app/code
COPY engine.py guardian_io.py secret_guardian.py http_api.py mobile.html mobile.js PROVENANCE.json .env secret-guardian.inventory.json /app/code/
COPY cases /app/code/cases
RUN find /app/code -type d -exec chmod 0555 {} + && find /app/code -type f -exec chmod 0444 {} +
USER 10001:10001
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ALDOL_SECURITY_ROOT=/app/code ALDOL_SECURITY_HOST=0.0.0.0 ALDOL_SECURITY_OSV_NETWORK=0
CMD ["python", "-B", "http_api.py"]
```

Fixtures: `.env` has one fake `OPENAI_API_KEY` assignment; root manifest has one ref `qa-synthetic-record`, provider openai, environment test, admin privilege, owner qa-team, rotation 2020-01-01, expiry 2020-02-01, 90-day policy, suspected exposure. `cases/invalid/secret-guardian.inventory.json` is deliberately invalid JSON; `cases/empty/.keep` is a harmless marker. `PROVENANCE.json` contains the source SHA and file/hash rows from the preflight. Synthetic world-read mode intentionally triggers its permission risk and does not represent real credentials.

Build locally with `docker build --network=none`; run with `--network none --read-only --cap-drop ALL --security-opt no-new-privileges --memory 128m --cpus 1 --pids-limit 64`. Generate a disposable synthetic token in the calling process and use `-e ALDOL_SECURITY_TOKEN` to inherit it without putting its value in arguments. Use an in-container standard-library HTTP client to request `127.0.0.1:8765`; do not publish ports. Remove the container afterward. The original destructive race/failure tests can be rerun safely with:

```sh
python -m unittest discover -s packages/security/tests -v
```

The local preparation/probe/runner scripts are retained alongside local evidence. Their outcome can be independently checked from the source hashes, recipe, fixtures and response expectations above. These commands do not authorize any remote deploy or credential change.

## Preservation comparison

Baseline was captured before mutations; readback completed at **2026-10-23 02:04:37 UTC**, after local/HTTPS checks. Final PR publication readback is recorded in PR #33.

| Item | Before → after |
| --- | --- |
| Production serving deployment | `dpl_E3N2X7WwkCQrgPcMok62xFrzXg14` → same |
| Production source / READY | `4246e6f7a664145a3f7b48a7ad4858022e99ddd2` / READY → same |
| Production aliases | All 13 observed alias bindings/update timestamps unchanged; three serving aliases still point to original deployment |
| Production settings | Observed project ID, owner, framework, updatedAt, domains, SSO protection unchanged |
| Production environment metadata | Names, IDs, types, targets, branch scopes and timestamps unchanged; secret values intentionally not read |
| Existing QA serving deployment | `dpl_HjTwRp7TBCE4pPMxdqSuCdzNKYHq` → same |
| Existing QA source / READY | `8866723527c7179b3d7bcf12bbdb83717e434c45` / READY → same |
| Existing QA aliases | Both bindings and update timestamps unchanged |
| QA settings/environment metadata | Observed fields unchanged; no mutations performed |
| main / base | Baseline SHAs above preserved; re-read at publication |
| PR #33 | Draft, open, unmerged; documentation update only |
| Complete deployment/permission audit history | BLOCKED — Vercel event API returned 403; no permission expansion attempted |

Snapshot equality is evidence of the observed current state, not a proof of every intervening action or secret-value equality. Gate D is therefore NOT_VERIFIED overall even though every observable preservation comparison passed.

## Failures, limitations and follow-up

- Deployment isolation preflight could not meet the user's preview/no-alias-change condition; no trial deployment was used to discover side effects.
- API domain filtering returned 400; corrected unfiltered query succeeded. Event query timestamp format was corrected; the valid ISO-date request then returned 403. These are metadata API limitations, not Guardian failures.
- The standard Dockerfile at the target SHA omits `guardian_io.py`. The tested QA-only recipe includes it; standard-container release remains blocked until a reviewed packaging fix and image test. No production recipe/project was changed here.
- Initial alias metadata included protection-bypass fields in transient tool output. They were neither used nor saved to reports/evidence; subsequent handling is allowlisted. Owner review of the existing link exposure is needed, separately from the application QA task. No revocation/auth change was made.
- Physical Android and authorized remote authentication remain blocked. See [device checklist](ANDROID_PHYSICAL_QA.md) and [release gates](SECRET_GUARDIAN_RELEASE_GATE.md).
