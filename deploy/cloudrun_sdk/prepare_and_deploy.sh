#!/usr/bin/env bash
set -euo pipefail
# Deploy ONLY a distinct Forge service inside the EXISTING Slack bridge project.
# The Slack receiver is read-only inventory and must never be redeployed here.
PROJECT="aram-slack-bridge-2026"
SLACK_SERVICE="slack-bridge-receiver"
FORGE_SERVICE="forge-sdk-verifier"
REGION="${REGION:?Set REGION to the confirmed existing Slack Cloud Run region}"
SECRET_REF="${FORGE_SDK_SECRET_REF:?Use an EXISTING Secret Manager secret reference, for example forge-sdk-hmac:latest}"
if [[ "${1:-}" != "--deploy" ]]; then
  echo "No resources changed. Pass --deploy after verifying IAM, secret, billing and GCP project."
  echo "Target GCP project: $PROJECT"
  echo "Preserve Slack service: $SLACK_SERVICE"
  echo "New isolated Cloud Run service: $FORGE_SERVICE"
  exit 0
fi
command -v gcloud >/dev/null || { echo "Missing gcloud CLI" >&2; exit 2; }
echo "Checking Slack service without modifying it"
gcloud run services describe "$SLACK_SERVICE" --project "$PROJECT" --region "$REGION" \
  --format='value(metadata.name)' >/dev/null
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../" && pwd)"
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
mkdir -p "$staging/bridge" "$staging/ci"
cp "$root/Dockerfile.forge-sdk-cloudrun" "$staging/Dockerfile"
for f in forge.py verify_sdk.py sandbox.py mcp_runtime.py templates.py openapi_forge.py api_runtime.py; do
  cp "$root/$f" "$staging/$f"
done
cp "$root/bridge/sdk_job_gateway.py" "$root/bridge/cloud_run_verifier.py" "$staging/bridge/"
cp "$root/ci/verify_studio_archive.py" "$staging/ci/"
# IAM is private by default. Do not grant allUsers access here.
gcloud run deploy "$FORGE_SERVICE" \
  --project "$PROJECT" --region "$REGION" --source "$staging" \
  --cpu 1 --memory 1Gi --concurrency 1 --timeout 120 \
  --min-instances 0 --max-instances 1 \
  --no-allow-unauthenticated \
  --set-secrets "FORGE_SDK_BRIDGE_SECRET=$SECRET_REF" \
  --set-env-vars "ALDOL_API_BASE_URL=,ALDOL_API_ALLOWED_HOST="
echo "Forge verifier deployed with IAM restriction. Slack receiver untouched."
echo "Sites requires a separately reviewed caller authentication path before SDK_BRIDGE_ENABLED=1."
