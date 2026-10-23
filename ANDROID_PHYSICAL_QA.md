# Android physical QA — 2026-10-23

**BLOCKED / NOT_VERIFIED.** No connected physical Android device, ADB control path, authenticated device session or completed owner test evidence is available. A device-availability question was sent; no device result has been received. Chromium emulation and local container tests are not physical-device verification.

Do not test the old QA URL and label it verification of the new source. Start only after an authorized isolated Preview has a recorded READY deployment ID and verified source SHA.

## Device evidence to record (no credentials)

| Field | Actual result |
| --- | --- |
| Device model | NOT_VERIFIED |
| Android version | NOT_VERIFIED |
| Chrome version | NOT_VERIFIED |
| Viewport, orientation, text/display scaling | NOT_VERIFIED |
| Network type (Wi-Fi/mobile; no SSID/IP needed) | NOT_VERIFIED |
| UTC date/time | NOT_VERIFIED |
| Unique Preview URL / Deployment ID | BLOCKED: none created |
| Runtime source SHA | Intended `01a519a522637c7e09fcddcf0d48b8701e972e31`; not verified on device |

## Owner checklist

1. Open the approved unique Preview URL in Android Chrome; record its deployment ID and source SHA.
2. Complete normal Vercel Authentication with an authorized owner account. Do not use a share/bypass link as evidence of an owner login.
3. Verify the dashboard and Guardian selector render correctly in portrait; inspect controls and horizontal overflow.
4. Obtain the QA-only Bearer token through the approved secret-management channel. Enter it only into the password field; never paste it into chat, PRs, URLs, screenshots or exported logs.
5. Select Guardian and scan the synthetic default workspace. Record only status, counts and risk codes; ensure no variable names, values, aliases or internal paths appear.
6. Scan twice; confirm report-scoped refs differ between reports while risk refs match records within each report. Do not treat refs as durable credential identities.
7. Rapidly tap the scan button during an active request; it must remain disabled and avoid duplicate UI submissions.
8. Use an intentionally incorrect, non-secret token; verify the authentication-failure message. Restore the valid token privately.
9. Test approved fixture subpaths `cases/invalid` and `cases/empty`; expect INCOMPLETE and UNKNOWN with “not a safety verdict” language. `../` must be BLOCKED. These fixture names apply only to the prepared candidate package.
10. Switch between portrait and landscape; check readable risk explanations, no unwanted horizontal scroll and usable touch targets.
11. Disable the device network briefly and submit; the connection-failure message must differ from authentication failure. Re-enable the network.
12. Refresh the page. Verify no token in URL/history and no application-stored token. Where available, use authorized Chrome remote debugging to check localStorage, sessionStorage and cookies without copying values. Browser/password-manager retention is a separate device setting and must be reported if unexamined.
13. Clear the token field before any result screenshot. Never capture login/password/token entry, request Authorization headers, cookies or HAR files. Return only sanitized checklist outcomes and device versions.

A legitimate authenticated request necessarily carries the Bearer token in an HTTPS Authorization header; the criterion is no persistence in application storage, URLs or diagnostic exports, not absence from the authorized network request. If browser/network-log inspection is unavailable, record NOT_VERIFIED.

## Acceptance record

All currently **NOT_VERIFIED**: actual owner login, touch operation, authenticated Guardian result, portrait/landscape layout, duplicate protection, authentication/network distinction, uncertain-state wording, token/storage privacy and refresh behavior.

Android Chrome success would not demonstrate remote MCP/OAuth transport or ChatGPT Android integration. Those remain separate scope.
