# RIGHTS v0.2 service implementation

User execution brief is the approved scope. Keep PR23 intact; implement on a child branch, never main.

Architecture: one FastAPI app on Vercel serves a responsive Korean frontend, authenticated REST API and official SDK 2.3 Streamable HTTP endpoint. Both adapters call a pure policy wrapper reusing core._usage. Existing local SQLite/stdio interfaces remain compatible. ARAM Supabase gets namespaced owner-scoped tables and private storage only. No global Auth changes, no service-role key.

Web uses Supabase password authentication with HttpOnly SameSite cookies and server-side identity validation. MCP uses separately generated 256+ bit opaque read-only connection keys; only SHA256 hashes persist; expiry and revocation are checked for every call. A narrow SQL security-definer RPC exposes only a token owner's RIGHTS rows and never writes. Plugin declares native API-key bearer authentication, no packaged credentials. OAuth is not claimed. Public read-only license reference can be tested independently.

Tasks (native execution, no delegation):
- [x] Add failing policy tests: four Korean statuses, legacy regression, GPL/manual, SA ambiguity, timestamp and missing evidence.
- [x] Implement shared policy and validated data models; retain original five stdio tools.
- [x] Add owner-isolated assets, checks and connection keys; private MIME/size-limited uploads; migration and RLS tests.
- [x] Implement authenticated API, reports, key revocation and HTTP error/security handling.
- [x] Build mobile frontend: login, dashboard, assets/form/detail/history/report, dark theme, fixed bottom navigation.
- [x] Add official SDK MCP read tools and bearer authentication; verify SDK client over HTTP.
- [x] Deploy dedicated necessary Vercel RIGHTS app; connect rights.aldol.app if verified; no Railway.
- [x] Test deployed persistence, cross-user access, private files, reports, and DOM offline retry. Desktop login browser PASS. 360px/landscape/touch/keyboard/device checks remain BLOCKED; see validation report.
- [x] Save source in GitHub PR25, create private plugin and attempt host connection. ChatGPT logged-out browser and physical Android checks remain BLOCKED, not complete.

Review focus: stale checks after edits; zero/large reports never partial; malicious URLs/files inert; invalid and revoked keys; duplicate writes on network retry. Store asset revision + check snapshot, cap explicit reports to 500, validate upload signature, fail closed and reuse browser-generated UUID idempotency keys.
