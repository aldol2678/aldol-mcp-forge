#!/usr/bin/env bash
# Source-stage verification using the actual standard Dockerfile.
# No external scanners, production endpoints, or published ports.
set -Eeuo pipefail
package_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="aldol-guardian-package-smoke:${GITHUB_RUN_ID:-local}"
container_id=""
cleanup() {
  if [[ -n "$container_id" ]]; then
    docker rm -f "$container_id" >/dev/null 2>&1 || true
  fi
  docker image rm "$image" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker build --target guardian-package -f "$package_dir/Dockerfile.vercel" -t "$image" "$package_dir"
synthetic_token="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
container_id="$(docker run --detach --network none --read-only \
  --cap-drop ALL --security-opt no-new-privileges \
  --memory 128m --cpus 1 --pids-limit 64 --user 10001:10001 \
  -e ALDOL_SECURITY_ROOT=/app/code \
  -e ALDOL_SECURITY_HOST=127.0.0.1 \
  -e ALDOL_SECURITY_OSV_NETWORK=0 \
  -e "ALDOL_SECURITY_TOKEN=$synthetic_token" \
  "$image" python -B http_api.py)"

# All probes run inside a network-isolated container against loopback.
# The synthetic token remains in process environments and is never printed.
docker exec "$container_id" python -B -c '
import http.client
import json
import os
import time

def request(method, path, payload=None, auth=None):
    conn = http.client.HTTPConnection("127.0.0.1", 8765, timeout=3)
    headers = {}
    if auth is not None:
        headers["Authorization"] = "Bearer " + auth
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()
    try:
        conn.request(method, path, body=body, headers=headers)
        res = conn.getresponse()
        return res.status, json.loads(res.read().decode())
    finally:
        conn.close()

for attempt in range(30):
    try:
        status, health = request("GET", "/health")
        assert status == 200 and health["status"] == "alive"
        break
    except (ConnectionError, TimeoutError):
        time.sleep(0.1)
else:
    raise AssertionError("local service did not start")

status, _ = request("GET", "/api/capabilities")
assert status == 401, "unauthenticated request was not rejected"
status, _ = request("POST", "/api/scan", {"tool": "guardian"})
assert status == 401, "unauthenticated POST was not rejected"
token = os.environ["ALDOL_SECURITY_TOKEN"]
status, caps = request("GET", "/api/capabilities", auth=token)
assert status == 200 and caps["name"] == "ALDOL SECURITY"
status, result = request("POST", "/api/scan", {"tool": "guardian", "subpath": "."}, auth=token)
assert status == 200, "authenticated Guardian POST failed"
assert result["module"] == "Secret Guardian"
assert result["reference_scope"] == "report"
assert result["reference_scheme"] == "hmac-sha256-64-v1"
assert result["status"] in ("UNKNOWN", "INVENTORIED")
assert result["credential_count"] == 0 and not result["risks"]
assert result["coverage"]["complete_within_local_scope"] is True
assert token not in json.dumps(result)
print("standard Dockerfile source-stage/Guardian loopback smoke: PASS")
'
