"""Private, bearer-guarded official MCP SDK v2 Streamable HTTP server for SEUM.

HTTP exposure is opt-in. No unauthenticated MCP operations or secret contents.
Railway terminates TLS at its edge; host allowlisting remains enabled in SDK.
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import re
from typing import Any

from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from .server import create_app

LOG = logging.getLogger("aldol.seum")
HOST_RE = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
PROBE: dict[str, Any] = {"status": "SKIP", "reason": "not requested"}


def _settings() -> tuple[bytes, TransportSecuritySettings]:
    token = os.environ.get("ALDOL_SEUM_MCP_BEARER_TOKEN", "")
    if (not isinstance(token, str) or not 40 <= len(token) <= 256
            or not token.isascii() or not all(33 <= ord(c) <= 126 for c in token)):
        raise RuntimeError("Private SEUM MCP bearer token must be set securely (40..256 printable ASCII chars)")
    domain = os.environ.get("ALDOL_SEUM_PUBLIC_HOST") or os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if domain:
        domain = domain.strip().lower()
        if (not HOST_RE.fullmatch(domain) or ".." in domain or "." not in domain
                or domain in ("localhost", "127.0.0.1")):
            raise RuntimeError("Invalid ALDOL_SEUM_PUBLIC_HOST")
        hosts = [domain, domain + ":*"]
        origins = ["https://chatgpt.com", "https://" + domain]
    else:
        # Start private. No public hostname accepted until explicitly configured.
        hosts = ["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*"]
        origins = ["http://127.0.0.1", "http://localhost"]
    return token.encode("ascii"), TransportSecuritySettings(
        allowed_hosts=hosts, allowed_origins=origins)


class PrivateSEUM:
    def __init__(self, inner: Any, secret: bytes):
        self.inner = inner
        self.secret = secret

    async def __call__(self, scope: dict, receive: Any, send: Any):
        if scope["type"] != "http":
            return await self.inner(scope, receive, send)
        path = scope.get("path", "")
        if path == "/healthz":
            # Health reveals no credential or GitHub source detail.
            return await JSONResponse({"service": "seum-mcp", "healthy": True})(
                scope, receive, send)
        if path not in ("/mcp", "/status"):
            return await JSONResponse({"error": "not_found"}, status_code=404)(
                scope, receive, send)
        # Examine raw ASGI headers to reject duplicate Authorization headers.
        values = [value for key, value in scope.get("headers", [])
                  if key.lower() == b"authorization"]
        valid = len(values) == 1 and hmac.compare_digest(
            values[0], b"Bearer " + self.secret)
        if not valid:
            return await JSONResponse(
                {"error": "authorization_required"}, status_code=401,
                headers={"www-authenticate": "Bearer", "cache-control": "no-store"})(
                    scope, receive, send)
        if path == "/status":
            return await JSONResponse(
                {"service": "seum-mcp", "github_read_enabled":
                 os.environ.get("ALDOL_SEUM_GITHUB_READ_ENABLED") == "1",
                 "startup_probe": dict(PROBE),
                 "official_sdk_runtime": True},
                headers={"cache-control": "no-store"})(scope, receive, send)
        return await self.inner(scope, receive, send)


def _startup_probe():
    if os.environ.get("ALDOL_SEUM_STARTUP_PROBE_ENABLED") != "1":
        return
    if os.environ.get("ALDOL_SEUM_GITHUB_READ_ENABLED") != "1":
        PROBE.update(status="FAIL", reason="github_read_disabled")
        return
    # The verification target is public and known. This does not touch
    # INHA WORLD, ARAM WORLD, user-private repositories or credentials.
    data = {"source": "github", "owner": "aldol2678",
            "repo": "aldol-mcp-forge", "path": "examples/pets_openapi.json",
            "ref": "main"}
    try:
        from .seum import analyze_code
        outcome = analyze_code(json.dumps(data, separators=(",", ":")))
        summary = json.loads(outcome["summary"])
        if not (summary.get("parse_ok") and summary.get("method") == "github-readonly-static"
                and summary.get("github_provenance", {}).get("git_blob_sha")):
            raise ValueError("Unexpected analysis outcome")
        provenance = summary["github_provenance"]
        PROBE.update(status="PASS", mode="live_github_get",
                     sha256=provenance["sha256"],
                     git_blob_sha=provenance["git_blob_sha"],
                     path=data["path"], ref=data["ref"])
    except Exception:
        # Do not leak errors, auth headers, network details or response bytes.
        PROBE.update(status="FAIL", reason="probe_unavailable")
    LOG.warning("SEUM_LIVE_GITHUB_PROBE status=%s", PROBE["status"])


def create_http_app():
    secret, security = _settings()
    sdk = create_app("seum")
    inner = sdk.streamable_http_app(
        host="0.0.0.0", streamable_http_path="/mcp",
        json_response=True, stateless_http=True, max_request_body_size=262144,
        transport_security=security)
    _startup_probe()
    return PrivateSEUM(inner, secret)


app = create_http_app()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    if not 1 <= port <= 65535:
        raise RuntimeError("PORT out of range")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning",
                workers=1, access_log=False)
