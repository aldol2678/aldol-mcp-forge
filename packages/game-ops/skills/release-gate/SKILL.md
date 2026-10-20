---
name: release-gate
description: Review readiness to ship or publish any ALDOL game, regardless of GitHub, pull requests or CI. Use for a new game version, playable site, platform release, local HTML/ZIP build, native client, PR merge or post-release verification.
---

# ALDOL Release Gate: platform agnostic

First apply `project-routing` unless the project's delivery path and current version are already verified. Inspect only the gate types that actually exist. A `PR` and CI are **not prerequisites** to release readiness. Never treat other games' repositories as relevant by default.

## Path-adaptive checks
- **Local HTML / independent artifact**: identify exact file/package, version/hash if available, entry point and dependencies; run or verify supported smoke tests and save/refresh flow, record how and where artifact would be distributed. No fictional commit SHA.
- **Third-party game platform / internal versioned editor**: verify actual platform project ID, current playable version and runtime behavior. A release claim requires platform readback; platform-generated edits and independent source copies are not assumed synchronized.
- **GitHub or other VCS when present**: verify branch/PR/review/CI conditions relevant to the user-authorized action, then check actual release separately. Match CI to current commit; avoid repetitive polling.
- **Unity/native PC/client package**: verify target platform, build/package ID, startup, error logs, save path, compatibility and distribution steps as relevant.
- **Web/3D/multiplayer**: verify required browser/device, scene startup, rendering path, join/leave/reconnect and performance or resource checks where relevant.

For all types: test critical gameplay loop, controls, UX/localization, regression, persistence, auth/security/payments where applicable, launch path, and rollback/recovery approach. Clearly separate static review, simulation, actual playback, platform readback, and physical device verification.

## Decision & action boundaries
- `READY`: required gate checks have concrete evidence for the **specified release target**. READY does not mean published.
- `BLOCKED`: an essential check failed.
- `UNKNOWN`: needed evidence or access is missing; say exactly what.
- For an approved external action, report separately `완료·검증됨`, `실행됨·검증 미완료`, `실패`, or `미확인` based on returned result and readback.
- `repository not found` or `no PR` is not a blocker for non-GitHub games.
- Never deploy/publish/merge/migrate/change permissions without a user-authorized scope. If the user approved one artifact or platform, do not infer approval for another.

## Output
Game/project; actual development and delivery path; version/build evidence (SHA only if exists); runtime and environment checked; tested vs not tested scenarios; READY/BLOCKED/UNKNOWN; what is needed next. Document verification time where available. Do not claim production complete from screenshots, proposals, old context or CI alone.
