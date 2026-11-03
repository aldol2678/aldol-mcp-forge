"""MAJUNG Cloudflare Python Worker: modern MCP 2026-07-28 adapter.

QA-only candidate. Supports stateless JSON responses, and explicitly rejects
unmatched mirrored headers to prevent header/body disagreement at intermediaries.
Live network source retrieval remains disabled by default.
"""
import base64
import binascii
import hmac
import json
from urllib.parse import urlsplit
from workers import WorkerEntrypoint, Response
from gateway import TOOL_SPECS, invoke_tool

MAX_BODY = 524288
BASE_HEADERS = {"cache-control": "no-store", "x-content-type-options": "nosniff"}
PROTOCOL = "2026-07-28"
SERVER = {"name": "ALDOL MAJUNG Cloudflare Candidate", "version": "0.2.0"}
IDENTITY = {"io.modelcontextprotocol/serverInfo": SERVER}
META_VERSION = "io.modelcontextprotocol/protocolVersion"
META_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"

def reply(value, status=200):
    return Response.json(value, status=status, headers=BASE_HEADERS)

def problem(req_id, code, message, status=400, data=None):
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return reply({"jsonrpc": "2.0", "id": req_id, "error": err}, status)

def valid_token(token):
    return (isinstance(token, str) and 40 <= len(token) <= 256
            and token.isascii() and all(33 <= ord(c) <= 126 for c in token))

def unmirror(value):
    """Decode the MCP sentinel only for mirror-value comparisons."""
    if value is None:
        return None
    value = str(value)
    if value.startswith("=?base64?") and value.endswith("?="):
        try:
            decoded = base64.b64decode(value[9:-2], validate=True).decode("utf-8")
        except (ValueError, UnicodeError, binascii.Error):
            return None
        return decoded
    if not value or not value.isascii() or any(ord(ch) < 32 or ord(ch) > 126 for ch in value):
        return None
    return value

def result(payload, *, cacheable=False):
    output = {"resultType": "complete", "_meta": IDENTITY, **payload}
    if cacheable:
        output.update({"cacheScope": "private", "ttlMs": 0})
    return output

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        u = urlsplit(str(request.url))
        path = u.path
        method = str(request.method).upper()
        origin = request.headers.get("origin")
        # Every cross-origin request is rejected. Server-to-server calls without
        # Origin remain allowed; any future browser origin requires explicit review.
        if origin is not None and str(origin) != (u.scheme + "://" + u.netloc):
            return reply({"error": "origin_rejected"}, 403)
        if path == "/healthz" and method == "GET":
            return reply({"company": "majung", "healthy": True})
        if path not in ("/status", "/mcp"):
            return reply({"error": "not_found"}, 404)
        token = getattr(self.env, "ALDOL_MCP_BEARER_TOKEN", None)
        if not valid_token(token):
            return reply({"error": "service_unconfigured"}, 503)
        given = request.headers.get("authorization")
        if not isinstance(given, str) or not hmac.compare_digest(given, "Bearer " + token):
            return Response.json({"error": "authorization_required"}, status=401,
                                 headers={**BASE_HEADERS, "www-authenticate": "Bearer"})
        if path == "/status" and method == "GET":
            return reply({"company": "majung", "authenticated": True,
                          "backend": "cloudflare-python-workers-candidate",
                          "live_search_enabled": getattr(self.env, "MAJUNG_LIVE_ENABLED", "false") == "true",
                          "remote_verified": False})
        if method != "POST":
            return reply({"error": "method_not_allowed"}, 405)
        if "application/json" not in str(request.headers.get("content-type") or "").lower():
            return reply({"error": "content_type_required"}, 415)
        size_header = request.headers.get("content-length")
        if size_header:
            try:
                if int(size_header) > MAX_BODY:
                    return reply({"error": "request_too_large"}, 413)
            except ValueError:
                return reply({"error": "invalid_content_length"}, 400)
        try:
            raw = await request.text()
            if len(raw.encode("utf-8")) > MAX_BODY:
                return reply({"error": "request_too_large"}, 413)
            message = json.loads(raw)
        except (ValueError, TypeError, UnicodeError):
            return problem(None, -32700, "Parse error")
        if (not isinstance(message, dict) or message.get("jsonrpc") != "2.0"
                or not isinstance(message.get("method"), str)):
            return problem(None, -32600, "Invalid request")
        req_id = message.get("id")
        if (isinstance(req_id, bool) or not isinstance(req_id, (str, int))):
            return problem(None, -32600, "Invalid request")
        params = message.get("params", {})
        if not isinstance(params, dict):
            return problem(req_id, -32602, "Invalid params")
        meta = params.get("_meta")
        version_header = request.headers.get("mcp-protocol-version")
        version = meta.get(META_VERSION) if isinstance(meta, dict) else None
        client_capabilities = meta.get(META_CAPABILITIES) if isinstance(meta, dict) else None
        name = params.get("name")
        # Modern Streamable HTTP requires all routing headers to agree with the
        # parsed JSON body. Validate before dispatching any tool.
        if (not isinstance(version, str) or not isinstance(client_capabilities, dict)
                or version_header is None or str(version_header) != version
                or str(request.headers.get("mcp-method") or "") != message["method"]
                or (message["method"] == "tools/call"
                    and (not isinstance(name, str)
                         or unmirror(request.headers.get("mcp-name")) != name))):
            return problem(req_id, -32020, "Header mismatch")
        if version != PROTOCOL:
            return problem(req_id, -32022, "Unsupported protocol version", 400,
                           {"supported": [PROTOCOL], "requested": version})
        def ok(value):
            return reply({"jsonrpc": "2.0", "id": req_id, "result": value})
        method_name = message["method"]
        if method_name == "server/discover":
            return ok(result({"supportedVersions": [PROTOCOL], "capabilities": {"tools": {}}},
                             cacheable=True))
        if method_name == "tools/list":
            return ok(result({"tools": TOOL_SPECS}, cacheable=True))
        if method_name == "tools/call":
            try:
                value = invoke_tool(name, params.get("arguments", {}),
                    allow_live=getattr(self.env, "MAJUNG_LIVE_ENABLED", "false") == "true")
                return ok(result({"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
                                  "structuredContent": value, "isError": False}))
            except (ValueError, TypeError, KeyError, OverflowError, OSError) as exc:
                # Only public input-validation errors are returned; never stack traces.
                return ok(result({"content": [{"type": "text", "text": str(exc)[:200]}],
                                  "isError": True}))
        return problem(req_id, -32601, "Method not found", 404)
