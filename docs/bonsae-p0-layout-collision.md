# BONSAE P0: real-rendered text collision checks

Status: isolated patch branch; not merged, deployed or released.

- Reuses the existing JavaScript-disabled, network-denied Playwright Chromium adapter.
- Detects bounded TEXT_TEXT and TEXT_MEDIA rectangle intersections at viewports 390/820/1280.
- Explicit data-bonsae-overlap="intentional" permits text-on-media within a marked region; text-text exemption requires marking both text owners.
- Existing return format remains compatible; browser.viewports[].overlaps, overlapCoverage and overlapPolicy are additive.
- Overlaps feed FAIL_RENDER_CHECKS, while the whole-screen PASS remains impossible; no browser yields HOLD_UNINSPECTED.
- Only the inspected viewport is covered (not full page), with bounded node counts and truncation indicators.
- Caveats: no z-order/occlusion, CSS background images, pseudo-elements or canvas inner-text inspection; rectangle overlap may produce false positives.
- ALDX: new fields are a future-compatible evidence shape only. No ALDX endpoint, handshake or protocol change is implemented.

Run locally with Chromium/Playwright installed:
python -m unittest enterprise_mcps.tests.test_bonsae_collision -v

No GitHub Actions, deployment, CI or main merge is required or authorized.
