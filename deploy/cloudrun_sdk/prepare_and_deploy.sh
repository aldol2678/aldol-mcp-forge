#!/usr/bin/env bash
set -euo pipefail
# This script never creates projects, APIs, repositories, accounts or IAM grants.
PROJECT="aram-slack-bridge-2026"
SLACK_SERVICE="slack-bridge-receiver"
FORGE_SERVICE="forge-sdk-verifier"
if [[ "${1:-}" != "--deploy" ]]; then
  echo "No resources changed. Pass --deploy from an authenticated GCP environment."
  echo "Target: $PROJECT / $FORGE_SERVICE; Slack receiver is read-only."
  exit 0
fi
REGION="${REGION:?Set REGION to the confirmed Slack Cloud Run region}"
SECRET_REF="${FORGE_SDK_SECRET_REF:?Set a Forge-only Secret Manager secret:version}"
RUNTIME_ACCOUNT="${FORGE_SERVICE_ACCOUNT:?Set the dedicated Forge runtime service account}"
[[ "$REGION" =~ ^[a-z]+-[a-z]+[0-9]+$ ]] || { echo "Invalid region" >&2; exit 2; }
[[ "$RUNTIME_ACCOUNT" == "forge-sdk-verifier@$PROJECT.iam.gserviceaccount.com" ]] || { echo "Dedicated forge-sdk-verifier identity required" >&2; exit 2; }
[[ "$SECRET_REF" =~ ^forge-sdk-[a-z0-9-]+:([0-9]+|latest)$ ]] || { echo "Only a Forge SDK secret is allowed" >&2; exit 2; }
command -v gcloud >/dev/null || { echo "Missing authenticated gcloud CLI" >&2; exit 2; }
command -v python3 >/dev/null
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../" && pwd)"
staging="$(mktemp -d)"
chmod 700 "$staging"
trap 'rm -rf "$staging"' EXIT
# Read-only prerequisites; failures stop before any build/deployment.
gcloud projects describe "$PROJECT" --format='value(projectId)' > "$staging/project"
[[ "$(cat "$staging/project")" == "$PROJECT" ]] || exit 2
gcloud billing projects describe "$PROJECT" --format=json > "$staging/billing.json"
python3 - "$staging/billing.json" <<'PY'
import json,sys
if json.load(open(sys.argv[1])).get('billingEnabled') is not True:
    raise SystemExit('Project billing not enabled; no billing changes attempted')
PY
gcloud run services describe "$SLACK_SERVICE" --project "$PROJECT" --region "$REGION" --format=json > "$staging/slack-before.json"
gcloud run services get-iam-policy "$SLACK_SERVICE" --project "$PROJECT" --region "$REGION" --format=json > "$staging/slack-iam-before.json"
gcloud iam service-accounts describe "$RUNTIME_ACCOUNT" --project "$PROJECT" --format=json > "$staging/runtime.json"
python3 - "$staging/slack-before.json" "$staging/runtime.json" "$RUNTIME_ACCOUNT" <<'PY'
import json,sys
slack,runtime=map(lambda p:json.load(open(p)),sys.argv[1:3])
if not any(c.get('type')=='Ready' and c.get('status')=='True' for c in slack.get('status',{}).get('conditions',[])):
    raise SystemExit('Slack service not Ready; stop before Forge deployment')
if slack['spec']['template']['spec'].get('serviceAccountName')==sys.argv[3] or runtime.get('disabled') is True:
    raise SystemExit('Runtime identity is disabled or shared with Slack')
PY
# Do not auto-enable paid APIs or auto-create an Artifact Registry repository.
gcloud services list --enabled --project "$PROJECT" --format='value(config.name)' > "$staging/apis"
for api in run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com; do
  grep -Fxq "$api" "$staging/apis" || { echo "Required API unavailable: $api; no APIs enabled" >&2; exit 2; }
done
gcloud artifacts repositories describe cloud-run-source-deploy --project "$PROJECT" --location "$REGION" --format='value(name)' >/dev/null
gcloud secrets versions describe "${SECRET_REF#*:}" --secret "${SECRET_REF%:*}" --project "$PROJECT" --format='value(state)' > "$staging/secret-state"
[[ "$(cat "$staging/secret-state")" == "ENABLED" ]] || { echo "Forge secret not enabled" >&2; exit 2; }
# Refuse upgrading a pre-existing public/bypassed Forge target.
gcloud run services list --project "$PROJECT" --region "$REGION" --format='value(metadata.name)' > "$staging/services"
if grep -Fxq "$FORGE_SERVICE" "$staging/services"; then
  gcloud run services get-iam-policy "$FORGE_SERVICE" --project "$PROJECT" --region "$REGION" --format=json > "$staging/forge-iam.json"
  gcloud run services describe "$FORGE_SERVICE" --project "$PROJECT" --region "$REGION" --format=json > "$staging/forge-before.json"
  python3 - "$staging/forge-iam.json" "$staging/forge-before.json" <<'PY'
import json,sys
policy,service=map(lambda p:json.load(open(p)),sys.argv[1:])
if any(m in ('allUsers','allAuthenticatedUsers') for b in policy.get('bindings',[]) for m in b.get('members',[])):
    raise SystemExit('Existing Forge service has public grants; no IAM changes attempted')
if service.get('metadata',{}).get('annotations',{}).get('run.googleapis.com/invoker-iam-disabled')=='true':
    raise SystemExit('Existing Forge service has IAM checking disabled')
PY
fi
mkdir -p "$staging/source/bridge" "$staging/source/ci"
cp "$root/Dockerfile.forge-sdk-cloudrun" "$staging/source/Dockerfile"
for f in forge.py verify_sdk.py sandbox.py mcp_runtime.py templates.py openapi_forge.py api_runtime.py; do
  cp "$root/$f" "$staging/source/$f"
done
cp "$root/bridge/sdk_job_gateway.py" "$root/bridge/cloud_run_verifier.py" "$staging/source/bridge/"
cp "$root/ci/verify_studio_archive.py" "$staging/source/ci/"
gcloud run deploy "$FORGE_SERVICE" --project "$PROJECT" --region "$REGION" \
  --source "$staging/source" --service-account "$RUNTIME_ACCOUNT" \
  --cpu 1 --memory 1Gi --concurrency 1 --timeout 120 --cpu-throttling --no-cpu-boost \
  --min-instances 0 --max-instances 1 --no-allow-unauthenticated \
  --set-secrets "FORGE_SDK_BRIDGE_SECRET=$SECRET_REF" \
  --set-env-vars "ALDOL_API_BASE_URL=,ALDOL_API_ALLOWED_HOST="
gcloud run services describe "$SLACK_SERVICE" --project "$PROJECT" --region "$REGION" --format=json > "$staging/slack-after.json"
gcloud run services get-iam-policy "$SLACK_SERVICE" --project "$PROJECT" --region "$REGION" --format=json > "$staging/slack-iam-after.json"
python3 - "$staging" <<'PY'
import hashlib,json,pathlib,sys
p=pathlib.Path(sys.argv[1])
load=lambda name:json.loads((p/name).read_text())
def stable(x):
    return {'spec':x['spec'],'annotations':x.get('metadata',{}).get('annotations',{}),
            'revision':x.get('status',{}).get('latestReadyRevisionName')}
a,b=map(stable,(load('slack-before.json'),load('slack-after.json')))
if a!=b or load('slack-iam-before.json')!=load('slack-iam-after.json'):
    raise SystemExit('Slack configuration drift observed; STOP Sites activation. No Slack repair attempted.')
print('Slack configuration/IAM unchanged; fingerprint:',hashlib.sha256(json.dumps(a,sort_keys=True).encode()).hexdigest())
PY
gcloud run services describe "$FORGE_SERVICE" --project "$PROJECT" --region "$REGION" \
  --format='yaml(metadata.name,status.url,status.latestReadyRevisionName,status.conditions)'
echo "Forge deployed privately. SDK_BRIDGE_ENABLED must stay 0 until IAM, HMAC and production E2E pass."
