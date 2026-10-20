---
name: agent-handoff
description: Prepare and review bounded implementation and QA tasks for ALDOL's AI collaborators on any game delivery path, with or without GitHub or an editable repository.
---

# ALDOL Agent Handoff

First identify the exact game, its runtime and editing/deployment source (or UNKNOWN). The user is the project designer and final decision maker. Preserve existing working UI/gameplay outside approved scope. Do not assume all games share a code repository, toolchain or canonical owner.

## Assignment structure
1. Goal and rationale; exact game identity, runtime, target project/editor or file version when verified.
2. In scope vs excluded edits, constraints, independent-edition boundaries, forbidden side effects.
3. Concrete acceptance scenarios for supported targets, regression tests, Korean localization quality, evidence and what constitutes not tested.
4. Expected deliverable **appropriate to the project**: HTML file/ZIP or hosted demo, platform project version, Unity client build, changed design/artifact, or PR+SHA **only if Git is actually used**.
5. Verification and handoff owner when grounded; no invented Slack channel or unasked dispatch.

## Approval and state
Distinguish `설계/제안`, `구현`, `테스트 실행`, `외부 반영`, `운영 검증`. A collaborator's self-reported PASS is evidence to inspect, not final approval. Read back persisted state when feasible, or report `실행됨·검증 미완료`. Never migrate non-Git games to GitHub just to comply with a template. No upload, external message, merge, publishing or permission change without action-specific authorization.
