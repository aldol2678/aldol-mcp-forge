---
name: game-qa
description: Plan or perform evidence-backed QA on ALDOL games across browser, third-party platforms, independent HTML builds, Unity/PC clients, 3D worlds and multiplayer. Do not assume GitHub or access to source code.
---

# ALDOL Game QA

Use `project-routing` to select playable runtime and target environment. **A QA session operates on the game that actually runs**, not automatically on the latest source, screenshot, development PR or a similarly named clone.

## Adapt the test matrix
- **All games**: launch/title, main gameplay loop, controls and feedback, win/lose/progression states, recovery/restart, navigation, language quality (including Korean particles, spacing and generated strings), regression, serious UX friction.
- **Browser / static HTML / platform-hosted web**: supported browsers, keyboard/mouse/touch, viewport/orientation, page visibility, reload and persistence when applicable; distinguish browser QA from mobile hardware QA.
- **Native/Unity/PC**: install or open correct package, supported OS, input/gamepad where relevant, window/fullscreen, frame stability, error logs, save/load, version identity.
- **3D/Multiplayer only when present**: renderer support/fallback, world load, camera and movement, sessions, disconnect/reconnect, sync and performance.
- **Monetization, security, networking and user-generated content**: test only if features exist; respect safe test-account/production boundaries.

## Evidence model
For each scenario, record `game`, `artifact/platform version`, `runtime`, `device/browser/OS`, `steps`, `expected`, `observed`, `PASS/FAIL/UNKNOWN`, `evidence link or log`, `checked time`. Version may be an artifact name or platform revision, not necessarily a Git SHA. Mark real-device tests UNKNOWN if only emulator/responsive browser was used. Screenshot/code review is not proof of actual play.

## Final report
List reproducible critical defects, major UX friction and cosmetics, plus tests not performed. Avoid merging results from independent editions or independent game projects. Never change a source file, platform build, merge or publish as part of QA without user authorization.
