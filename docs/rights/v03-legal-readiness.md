# ALDOL RIGHTS v0.3 · Legal policies and data-subject controls
Status: **SOURCE PATCH / DRAFT PR. Not deployed; NOT legal approval.**

## Scope
- Persistent public notices at `/privacy`, `/terms`, plus SPA views and footer links.
- Versioned, immutable-after-publication legal documents, isolated policy administrator registry.
- Registration requires published privacy notice and accepted current terms. Formal acceptance ledger entry is created at the first authenticated use; sign-up checkbox alone is not a persisted receipt if email confirmation is pending.
- Latest published **effective** version gates RIGHTS writes (asset create/edit/check/upload, API key creation). Reading existing data and privacy rights requests remains possible without acceptance.
- Authorized editor: create draft, edit with optimistic revision check, review and publish. Published text cannot be edited; open a new version.
- Privacy center: scoped metadata export (not complete archive), access/rectification/erasure/restriction request **intake only**. Requests do not automatically delete data or alter shared ARAM authentication.
- MCP remains exactly six read-only remote tools. No change to keys, scopes, original files or the original v0.2 engine.

## Operational release prerequisites
1. Confirm actual controller/operator legal name, contact, applicable statutory notices, authentic retention and disposal schedules including backups, subprocessors, data transfers/regions (Supabase/Vercel), and minors eligibility, with appropriate legal/privacy review. Source drafts contain [확인 필요] and **cannot** pass publishing gate.
2. Apply `packages/rights/service/sql/002_legal_policies.sql` after v0.2 schema in the correct ARAM project. Review RLS and actual database grants. The SQL is not an authorization to update shared Auth or other products.
3. Read back verified RIGHTS owner Auth UUID from the trusted Supabase Auth admin console, then grant exactly that UUID with privileged, audited SQL:
   `insert into public.rights_policy_admins(owner_id) values ('<VERIFIED_UUID>');`
   Never grant admin by user-controllable email or `user_metadata`. By default **no administrator is provisioned**.
4. On the staged instance, create reviewed draft documents using the administrator UI. Publish a valid terms document and privacy notice with actual effective date. Test public URLs as logged-out visitor, and validate existing member access and new signup separately.
5. Run tests, Node JS syntax checks, cross-account RLS checks, forged admin rejection, published-document immutability, version-change reacceptance, concurrent edits, upload/inspection regressions, mobile landscape/portrait/touch and Android ChatGPT app paths.
6. Independently review user requests, verify identity before fulfillment, record resolution in an authorized process, and avoid deleting the shared ARAM Auth account without an explicit scope decision.
7. Only after the above use staged-to-production approval and actual readback to mark as deployed. PR remains Draft. **No migration, site deployment, registration, or policy publication is performed by the source patch.**

## Legal design limits
- Generic wording is never sufficient evidence of compliance. Article 30 of the Korean Personal Information Protection Act requires accurate disclosed items; Article 22 distinguishes consent conditions. Policy notice acknowledgement is not a replacement for separately required consent.
- The manuscript does not assert that Vercel/Supabase are domestic-only, that all records have fixed retention, or that replacing assets deletes old storage blobs.
- The app cannot yet perform automatic account erasure, full historical exports, verified delivery of rights requests, rejection/appeal handling, or data-subject request SLA tracking. Intake is intentionally described as incomplete.
- Current admin edit is a plaintext legal document field; rich HTML is not interpreted. Server-rendered public text is escaped.
- Policy editor administrator writes remain protected by RIGHTS-specific RLS, not by hidden UI routes alone.
- User account acceptance is recorded after an authenticated session; unauthenticated signup consent intents are not falsely recorded.
