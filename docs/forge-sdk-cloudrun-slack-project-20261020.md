# Reuse the 2026-10-20 Slack bridge GCP project for Forge SDK

## Existing production boundary

- Existing GCP project: `aram-slack-bridge-2026`
- Existing Slack Cloud Run service: `slack-bridge-receiver`
- Existing Slack webhook: `/slack/events`

The bridge is already in use. **Do not replace its image, change its routes,
environment variables, IAM policies, traffic allocation, or revision.**

Use the same Google Cloud **project** for credentials, accounting and visibility,
but make the SDK verifier a **second independent Cloud Run service** named
`forge-sdk-verifier`. This may incur additional usage charges, even within the
same billing project. Do not provision the service until the user approves any
new billable service.

## Why the synchronous design matters

Cloud Run's default request-based billing allocates CPU during requests, not
after responding. The existing asynchronous `sdk_job_gateway.py` starts a
background thread and relies on process-local status files. That behavior is
not dependable on scale-to-zero/restarts and would risk lost jobs and false
UNKNOWN states.

New `bridge/cloud_run_verifier.py` receives a single **signed server-to-server
HTTPS POST**. It checks owner/project/artifact hash and HMAC signature, verifies
the ZIP byte contents against original Forge generator source, executes
official Python MCP SDK 2.0.0 using BOTH memory and stdio transports, returns
a final PASS/FAIL in that same HTTP response, and deletes temporary ZIP bytes.
No separate process needs to survive after the response.

With `SDK_BRIDGE_MODE=cloudrun-sync`, the authenticated **Sites Worker**
stores the final verified result in the **existing owner-partitioned R2
bucket**. On refresh it is read from R2, so Cloud Run can scale to zero.
No Slack shared data or durable filesystem volume is required.

## Safety sequence (GCP operator / Work)

1. READ ONLY: list existing `slack-bridge-receiver` revision, region,
   deployment URL, health/event logs, IAM policy and billing. Verify no staged
   changes are waiting to be deployed. Do not touch production.
2. Review budget/credit state, Cloud Run availability, and expected cost of a
   second service. Do not assume the project is free.
3. Obtain explicit approval to create an additional billable service, if needed.
4. Reserve a fresh 32+ random-byte HMAC secret in Google Secret Manager.
   Do not reuse Slack signing secret or Slack bot credentials.
5. Choose the existing Cloud Run region based on actual inventory. Do not guess.
6. Build from the **whitelisted** root Dockerfile context by running:
   ```bash
   export REGION="YOUR_VERIFIED_REGION"
   export FORGE_SDK_SECRET_REF="YOUR_EXISTING_GCP_SECRET_NAME:latest"
   bash deploy/cloudrun_sdk/prepare_and_deploy.sh --deploy
   ```
   The script only deploys **`forge-sdk-verifier`**, max 1 instance, request CPU
   with min instances 0, concurrency 1, Python 3.12 + official SDK 2.0.0,
   initially `--no-allow-unauthenticated`. It first checks the Slack service
   still exists and never redeploys it.
7. Establish a **Sites-compatible authenticated HTTPS invoker**. Important:
   a Cloud Run IAM-private service requires a valid Google ID token; a
   signed application HMAC request alone is **not** a Cloud Run Invoker token.
   Preferred solution: a least-privilege trusted proxy that validates Sites
   HMAC and invokes Cloud Run with an IAM-approved Google identity.
   If instead opting for Cloud Run public invoker permission, this is an
   intentional security/rights expansion requiring separate approval and
   abuse/rate-limit/cost controls. Application-level HMAC remains mandatory.
8. After proving real signed Site → Cloud Run SDK E2E with actual user identity,
   set **server-side only** in the existing owner-private Sites deployment:
   `SDK_BRIDGE_MODE=cloudrun-sync`,
   `SDK_BRIDGE_URL=https://VERIFIED_ENDPOINT/v1/sdk/jobs`,
   `SDK_BRIDGE_ORIGIN=https://VERIFIED_ENDPOINT`,
   `SDK_BRIDGE_SECRET=<protected fresh secret>`.
   Set `SDK_BRIDGE_ENABLED=1` **last**.
9. Verify Studio button: saved v0.2.1 curated project → SDK PASS from real
   in-memory + stdio → reload → same PASS from R2. Verify unauthorized user 403,
   invalid signatures 401, corrupted ZIP rejection, Slack `/slack/events`
   still HTTP 200, and baseline Slack task delivery.
10. Report Cloud Run service ID/URL, actual IAM/invoker controls,
    SDK log evidence (without artifacts or secrets), actual cost configuration,
    Sites version/deployment ID and the Slack bridge regression result.

## Not done automatically by this code branch

- No GCP account/Cloud Run management connector is available here.
- No Cloud Run service or Secret Manager value has been created.
- Existing Slack bridge configuration, routes, image, and IAM are unchanged.
- Existing ChatGPT Sites v7 remains live; SDK button remains SKIP until its
  authenticated execution host is actually connected.
- PR #11 is stacked on PR #9; neither is merged by this task.

## Local / CI verification

`node --test adapters/sites/tests/cloud_run_sdk.test.mjs` exercises Sites
HMAC payloads, final response checks, R2 persistence and owner isolation.

`node ci/generate_studio_sdk_fixtures.mjs` followed by
`python -m unittest bridge.test_cloud_run_verifier -v` invokes actual
official Python SDK v2 memory + stdio inside the HTTP request.

The GitHub Actions CI workflow exercises these paths without spending GCP
credits or deploying a service.

References:
- https://docs.cloud.google.com/run/docs/configuring/billing-settings
- https://docs.cloud.google.com/run/docs/authenticating/service-to-service
- https://docs.cloud.google.com/run/docs/deploying-source-code
