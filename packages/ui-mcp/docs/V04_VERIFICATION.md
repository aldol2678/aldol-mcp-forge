# v0.4 candidate verification — 2026-10-23 KST

This file records pre-commit local evidence. Current remote CI and deployment
results are read back and appended to the Draft PR description after commit.

| Deliverable | State | Evidence / scope |
|---|---|---|
| Existing code/dependency inspection | 완료·검증됨 | #19 → #27 → #28; baseline in REFERENCE_VISUAL_V04.md |
| Replica review and license | 완료·검증됨 | pinned upstream, `_regions` attribution, full MIT notice |
| Two new engine/tool implementations | 완료·검증됨 | `ui_core/reference.py`, `visual.py`, `server.py` |
| Input/output contracts and examples | 완료·검증됨 | `schemas/`, REFERENCE_VISUAL_V04.md |
| Existing UI/BONSAE integration | 완료·검증됨 | static draft → importer → validation/generation/audit/review; real BONSAE regression |
| Unit tests | 완료·검증됨 | 115/115: 78 legacy + 37 new; `evidence/v04/local/unit.txt` |
| MCP stdio | 완료·검증됨 | legacy 29 scenarios + new 22, ten-tool discovery |
| MCP standalone HTTP | 완료·검증됨 | 29 + 22 scenarios, 6 auth/body/Origin/Host checks |
| Vercel ASGI mounts, local | 완료·검증됨 | 29 + 22 UI scenarios, 6 security checks; BONSAE 3-tool discovery + analyze_design call |
| Existing browser behavior | 완료·검증됨 | HUD/dashboard, 4 sizes each; React consumer; real BONSAE output at 390/820/1280 |
| New visual browser checks | 완료·검증됨 | 24 comparisons: 2 real repository examples × 4 widths × identical/shift/missing |
| Jamo actual files | 완료·검증됨 | 8 initial captures, 4 version comparisons, 3 popup comparisons; observations below |
| GitHub Draft PR / remote CI | 미확인 at source commit | authoritative later result is in PR description |
| Isolated remote deployment / SDK calls | 미확인 at source commit | authoritative later result is in PR description |
| ChatGPT host candidate calls | 미확인 | SDK is not ChatGPT; private plugin configuration not changed |
| Android physical device | 미확인 | no device session; Chromium emulation only |
| Android custom MCP setup | 차단됨 | official custom-connection docs say web only; installed plugin use is a separate unverified route |
| UI quality approval / official adoption | 미확인 | neither requested nor claimed; no merge or production promotion |

## Actual observations

Repository examples: `expedition-hud-v03` is an existing illustrative expedition
HUD, not a claim to have tested the deployed Little Legion game. `web-dashboard`
is the repository example. Extracted 8 and 9 static components respectively.
Each had recognized buttons/panels and interaction candidates. Existing behavior
tests checked toggles/Escape, host bindings, events, 44px targets and overflow.

Jamo Library inputs were actual user project files, not synthetic substitutes:
- `jamo-alchemy-v0.3.1.html`, SHA256
  `72a9eef7ec0d84d0de7e41cbb5ad6e36ba35c14be5ab6ce5058eea547058732f`.
- `jamo-alchemy-v0.3.3.html`, SHA256
  `d1dc0ca1c5d70062d2cde9da5a9b5a056890ebbb03d0a6856dcdb97203ce2bbb`.

Raw private source files are not copied into this public repository. Reproduction
requires those files via the optional test arguments; CI reports Jamo NOT_RUN
without them. Static v0.3.3 inventory found 43 components and fixed/scroll/media
evidence. Source output is bounded and source copy/script/values are not echoed.

At 360, 390, 768 and 1280px both versions had no horizontal page overflow or
JavaScript page errors in the observed initial state. Opened classic editor:

| Viewport | Panel y / height | Visible scroll height / content | Interpretation |
|---|---|---|---|
| 360×780 | 220 / 560 | 495 / 581 | panel within viewport, inner scroll required |
| 390×844 | 284 / 560 | 495 / 581 | panel within viewport, inner scroll required |
| 768×1024 | 434 / 590 | 525 / 585 | panel within viewport, inner scroll required |

These are measured layout observations. Full editing without scrolling is not
proven and is false for the measured scroll containers. No game patch or gameplay
acceptance was performed. Initial and popup are deliberately different states;
their difference is not a regression verdict.

Representative 390px observations (scores are diagnostic only):
- Dashboard card translated 48px: layout similarity 0.947463, pixel difference
  0.016533, one coarse changed region. A high overall similarity still flags change.
- Jamo 0.3.1 → 0.3.3: similarity 0.743950, pixel difference 0.146099, two regions.
- Jamo popup closed → open: similarity 0.512895, pixel difference 0.603755, one region.

Selected before/after/mask images and JSON reports are committed under
`evidence/v04/browser`. The complete browser output can be regenerated; CI uploads
its generated evidence artifact. Binary masks can still expose shape information.

## Failures encountered and resolved / limitations retained

- Direct git clone failed in this runtime; used authenticated GitHub API snapshot
  and inherited Git-tree updates, without changing existing branches.
- Default Chromium download returned an invalid ZIP. Used existing real Chromium
  153.0.8010.0; no mock screenshots. A font install via apt failed; used local
  @fontsource Noto Sans KR 5.3.1 for final normalized screenshot evidence.
- Some PNG screenshots exceeded 180KB. Kept the server limit; captured explicit
  JPEG quality 75 rather than altering dimensions/limits.
- Local HTTP clients tried the runtime SOCKS proxy and failed for missing socksio.
  Test clients now bypass environment proxies only for loopback URLs; remote
  requests retain environment configuration.
- An initial popup measurement happened during its CSS transition. Waited for the
  final state and remeasured; the final panel is within the viewport. Initial
  intermediate measurements are not presented as product defects.
- Screenshot semantic recognition is not implemented. CSS cascade, computed
  geometry and behavior are outside the static analyzer. Edge comparison is
  heuristic, with contrast/font/capture caveats.
- Rate limiting across Vercel instances, browser/PWA auth/UI and Android physical
  device tests remain outside P0; no unverified capability is marked PASS.

## Scope preservation and regression risk

Core rendering/validation/anti-slop policies are unchanged; catalog has one
additive extension field. Server adds two tools, so hosts with frozen discovery
must explicitly refresh only after separate approval. Existing eight input/output
contracts are preserved, including all three schema versions and TSX/HUD/HTML.
New dependencies are Pillow and tinycss2 in UI requirements; root already used
Pillow. Decoder/parser versions and cold-start/runtime budgets need continued
maintenance. Per-process single-flight comparison reduces concurrent memory;
multiple serverless instances remain independently bounded.

No Railway use, main update, database mutation, production alias update, user
permission change, private plugin update, payment or game-state access occurred.
