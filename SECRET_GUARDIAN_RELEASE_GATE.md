# Secret Guardian release gates — 2026-10-23

**Overall: BLOCKED. Remote QA Verified = false. Android Verified = false.**

Runtime source is `01a519a522637c7e09fcddcf0d48b8701e972e31`. The new commit delivers documentation only; it neither changes nor deploys the runtime. [Existing exact-source CI](https://github.com/aldol2678/aldol-mcp-forge/actions/runs/39884130684) is successful. No release or merge approval is implied.

| Gate | Status | Basis |
| --- | --- | --- |
| A — Source Provenance | PASS (source/package scope) | Exact GitHub SHA/CI, six source hashes and distinct QA project verified. Does not certify a running new remote deployment. |
| B — Remote QA | BLOCKED | New protected Preview was not created because target/alias isolation could not be established; authorized client token/session absent. |
| C — Android Physical | BLOCKED | No device/controller/session/results and no new isolated endpoint. |
| D — Preservation | NOT_VERIFIED overall | Observable state comparisons PASS; full deployment/permission event-history query returned 403, and secret values were deliberately not compared. |

## Gate details

| Requirement | Status |
| --- | --- |
| Target Git SHA, existing PR/Draft and CI checked | PASS |
| QA project ID/owner distinct from production | PASS |
| Exact application files in local QA package/container | PASS |
| New remote Preview READY / correct source / protected | BLOCKED |
| Remote valid Bearer Guardian POST / no leak / negative tests | BLOCKED |
| Existing old QA rejects unauthenticated requests at Vercel gate | PASS for four GET paths only; not new-runtime proof |
| Existing QA aliases preserved | PASS (observed bindings/timestamps) |
| Android model/versions/owner login/touch/scan/UI/privacy | BLOCKED / NOT_VERIFIED |
| Production deployment/source/domains/aliases preserved | PASS (observed metadata) |
| Production and QA environment settings preserved | PASS for metadata/no performed writes; values NOT_VERIFIED |
| main/base preserved; PR Draft/open/unmerged | PASS (readback; documentation branch advances only) |
| Deployment and permission history completely reviewed | BLOCKED (403); no permission escalation |

## Concrete remaining conditions

1. **Preview execution path:** provide an already authorized deployment interface/session that can establish Preview targeting and preserve existing aliases before mutation. Preview itself is already authorized by the execution instruction; do not request that same permission again. Do not substitute production/staged-production deployment. If the available method needs QA production replacement or alias switching, obtain separate explicit approval for that exact action first.
2. **Dual authentication:** supply a normal authorized owner session and QA-only Bearer credential through an approved secret injection path. Never send the token in chat/PR/logs. Any change to QA auth/environment configuration needs separate approval. Do not create/reuse bypass links as a substitute for the requested owner-auth test.
3. **Android:** after an isolated READY Preview exists, owner completes the physical checklist and supplies only device/version/time/Deployment ID and sanitized outcomes. No screenshots of login/token entry or HAR exports.
4. **Audit:** owner provides a sanitized project-scoped deployment/permission history covering the verification window, or a permitted read-only audit path. No permission expansion is authorized here.
5. **Metadata incident:** owner reviews the existing protection-link exposure from the initial connector response. Any removal/revocation or auth changes require their separate authorization; no value is reproduced in deliverables.
6. **Standard image packaging:** before any standard-image release, review the missing `guardian_io.py` copy, rerun image startup/HTTP checks, and verify the resulting source version. The local QA-only image already includes it, but is not deployed.

## Residual risk register

| Severity | Risk and evidence | Impact / follow-up |
| --- | --- | --- |
| High until reviewed | Existing protection-link fields appeared in transient alias tool output; never used or saved in evidence | Owner evaluates exposure and authorizes any needed link invalidation; keep subsequent metadata output allowlisted. |
| High if ignored | Prior Preview request became QA production; no current pre-mutation alias guarantee | Could replace existing QA target/alias. Remain blocked until exact Preview isolation is established. |
| Medium | No authenticated remote Guardian POST or physical Android evidence | Local passes cannot predict protected-edge/device behavior; execute pending gates. |
| Medium | Standard Dockerfile omits new module | Standard container can fail startup; separate reviewed packaging correction before release. |
| Medium | Full audit history unavailable (403) | State snapshots cannot prove every intervening change; obtain sanitized owner audit evidence. |
| Medium | Mutable-host isolation and heuristic/self-reported inventory limits persist | Continue immutable mounts, worker isolation and manual interpretation; no breach/safety claim. |

Docs: [preflight](REMOTE_QA_PREFLIGHT.md), [test report](REMOTE_QA_REPORT.md), [Android checklist](ANDROID_PHYSICAL_QA.md). Keep existing PR #33 Draft. Do not merge, promote, deploy production, alter credentials or expand access on the basis of this report.
