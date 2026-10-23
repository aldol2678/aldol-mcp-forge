# Remote QA preflight — 2026-10-23 UTC

Decision: **DEPLOYMENT_BLOCKED / AUTH_BLOCKED**. No Vercel deployment/create/promote/alias/auth/environment-variable mutation was performed. This is not Remote QA Verified.

## Source and ownership

- Repository: `aldol2678/aldol-mcp-forge`; existing [Draft PR #33](https://github.com/aldol2678/aldol-mcp-forge/pull/33).
- Runtime source: `01a519a522637c7e09fcddcf0d48b8701e972e31`; remote PR HEAD matched before this documentation-only update. The runtime files are unchanged by this report commit.
- Base: `4246e6f7a664145a3f7b48a7ad4858022e99ddd2`; main: `db3cf756dcbcb3e79bfe7cf9c9ffada33c19c60b`.
- [CI 39884130684](https://github.com/aldol2678/aldol-mcp-forge/actions/runs/39884130684): re-read as completed/success with the exact runtime source SHA. Earlier unit/SDK/browser results do not prove a remote or Android result.
- Verified owning team: `aldol`, account ID `team_mmhYFLKGX6D7101sRtZ1Ifpu`. QA and production are distinct projects in that same team, not isolated accounts.

| Property | Independent QA | Production service |
| --- | --- | --- |
| Project | `aldol-secret-guardian-qa` | `aldol-security-mcp` |
| ID | `prj_oyesRiJYD1AohHrRBku2v1E6UcMO` | `prj_R4pgaHacNiB6qOf9GbUGj1IEoIRv` |
| Serving deployment | `dpl_HjTwRp7TBCE4pPMxdqSuCdzNKYHq` | `dpl_E3N2X7WwkCQrgPcMok62xFrzXg14` |
| Serving SHA | `8866723527c7179b3d7bcf12bbdb83717e434c45` | `4246e6f7a664145a3f7b48a7ad4858022e99ddd2` |
| State / target | READY / production **of QA project** | READY / production |
| Main hostname | `aldol-secret-guardian-qa.vercel.app` | `aldol-security-mcp.vercel.app` |
| Protection | Vercel Authentication enabled, `deploymentType=all` | Vercel Authentication enabled, `deploymentType=all` |

QA's two aliases both resolve to its existing deployment. The production service's three serving aliases resolve to its original deployment. Other pre-existing branch-preview aliases exist in the production project; a pre-existing unrelated `feat-ui-reference-visual…` deployment is ERROR. A project's latest deployment record is therefore not its serving production deployment. Neither was changed or scanned during preflight.

## Environment-variable metadata only

`filter_project_envs(decrypt=false)` was used; values were excluded from output/evidence and no decrypted-secret endpoint was used.

| Project | Name | Type | Scope |
| --- | --- | --- | --- |
| QA | ALDOL_SECURITY_TOKEN | sensitive | production (separate record) |
| QA | ALDOL_SECURITY_TOKEN | sensitive | preview (separate record) |
| QA | ALDOL_SECURITY_ROOT | plain | preview |
| QA | ALDOL_SECURITY_HOST | plain | preview |
| QA | ALDOL_SECURITY_OSV_NETWORK | plain | preview |
| Production | ALDOL_SECURITY_TOKEN | sensitive | production |
| Production | ALDOL_SECURITY_TOKEN | sensitive | preview, base feature branch only |

The records have different project/variable IDs. Token value independence is **NOT_VERIFIED**: values were intentionally not retrieved or compared. No authorized QA client token file/environment injection or authenticated owner-browser session is available to this runner. The preview token's existence does not supply authorization for a client request.

## Workspace and candidate package

The existing QA deployment file tree and its Dockerfile were read through Vercel's source-file API. Its declared workspace is `/app/code`; the recipe copies the HTTP application, mobile assets and synthetic metadata there and runs as a non-root scanner user. It contains no external scanner binaries. This confirms the declared recipe, not independently the running filesystem or environment overrides.

A new **local-only** minimal QA package was prepared from six exact Git blobs, plus explicitly synthetic fixtures, a provenance manifest and a QA Dockerfile. No real `.env`, cloud credentials or repository-wide workspace was copied. `guardian_io.py` is included. The standard repository `Dockerfile.vercel` at the target SHA omits this newly required module; do not use that recipe unchanged for this version. The separate QA recipe avoids that packaging defect without editing production configuration.

Source file hashes:

| File (`packages/security/`) | SHA-256 |
| --- | --- |
| `engine.py` | `ec0df8b79648001f332084fe20ea23bd46cee0e86901ca974f8987138b8eca84` |
| `guardian_io.py` | `d22b6800f21b45aa4df39cff56670f70ec7ff245c9fd8a5f56eb7f8bdbcac403` |
| `secret_guardian.py` | `f6e7eba899c6980782e2490d89d4e001e9abe2b036f7a1ca072ced6c64ab5a89` |
| `http_api.py` | `409e0c78a70684045c2747a6d9b0d5c654f9b76b7819f23cc0e26c0527c5388d` |
| `mobile.html` | `a319e53d8f78df31a600e623e74f93fd2c9bfe35c2bcc97c74fae156962d7fc1` |
| `mobile.js` | `93acb1dd44ec2eae5c1c47be85f785418cb9d14280b44f84a8d0475fac1a22f0` |

Pinned QA base image: `python:3.12-slim-bookworm@sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70`.

Synthetic fixtures: one dotenv name/value candidate and one metadata record with self-reported suspected exposure, expired date, overdue rotation and broad privilege; `cases/invalid` has malformed metadata; `cases/empty` has no inventory. The candidate's default workspace remains `/app/code`, matching the earlier declared recipe; future deployment must still confirm existing preview environment configuration without exposing values.

## Preview / Alias gate

- Existing QA is already classified `production`; its aliases must not move.
- Available MCP `create_deployment` accepts `target`, but exposes no explicit automatic-alias suppression setting or dry-run preview of resulting alias assignments. No deployment call was made to discover its behavior experimentally.
- The previous QA provisioning requested Preview but resulted in production. General Preview documentation is insufficient evidence that this project's next API deployment will preserve both its target and existing aliases.
- A target-filtered project-domain query returned HTTP 400. Retrying the unfiltered metadata query with the known team ID succeeded: the configured QA domain has `gitBranch=null`, `customEnvironmentId=null`, and is verified. This does not prove the next deployment's alias policy.
- Vercel CLI is not installed/authenticated here; its existing authentication file and token configuration are absent. No login or token retrieval was attempted.
- Official documentation describes `--skip-domain` together with `--prod`; using that production workaround is outside the explicit Preview-only approval. See [deploy CLI](https://vercel.com/docs/cli/deploy) and [create deployment API](https://vercel.com/docs/rest-api/deployments/create-a-new-deployment).

**Result: DEPLOYMENT_BLOCKED.** No new deployment ID or URL exists. An owner must establish a supported Preview-only, unique-URL path with existing-alias preservation before deployment. If it requires changing QA aliases, replacing QA production, or modifying auth/environment variables, obtain the additional approval required by the execution instruction.

## Authentication gate and metadata incident

The protected-fetch connector explicitly creates/reuses a temporary authentication bypass link, so it was not used. No share link, automation bypass or password-protection change was created. Normal unauthenticated HTTPS GETs to the old QA URL were tested separately (see report).

An initial alias-list API response unexpectedly included existing protection-bypass fields, and those fields appeared in transient tool output before the response was narrowed. The values were not used, not written into these documents, and not copied into saved evidence. All subsequent alias handling allowlists only hostname, project ID, deployment ID and update timestamp. This incident means “no sensitive metadata ever appeared in tool output” is **not** a valid claim. Owner review of the existing share-link exposure is recommended; revocation/auth changes were not performed because they require separate authorization.
