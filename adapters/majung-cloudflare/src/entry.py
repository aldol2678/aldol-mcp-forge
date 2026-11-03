"""Private MAJUNG JSON-RPC MCP entrypoint for Cloudflare Python Workers.

Intentionally an isolated candidate. Transport is checked locally; hosted
Python/SDK 2.0 compatibility must be proven before changing Sites.
"""
import hmac
import json
from urllib.parse import urlsplit
from workers import WorkerEntrypoint, Response
from gateway import TOOL_SPECS, invoke_tool

MAX_BODY = 524288
BASE_HEADERS = {"cache-control": "no-store", "x-content-type-options": "nosniff"}
PROTOCOL = "2026-07-28"

def reply(value, status=200):
    return Response.json(value, status=status, headers=BASE_HEADERS)

def valid_token(token):
    return isinstance(token, str) and 40 <= len(token) <= 256 and token.isascii() and all(33 <= ord(c) <= 126 for c in token)

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        path = urlsplit(str(request.url)).path
        method = str(request.method).upper()
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
        if path == "/status":
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
            payload = json.loads(raw)
        except (ValueError, TypeError, UnicodeError):
            return reply({"jsonrpc": "2.0", "id": None,
                          "error": {"code": -32700, "message": "Parse error"}}, 400)
        if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0" or not isinstance(payload.get("method"), str):
            return reply({"jsonrpc": "2.0", "id": None,
                          "error": {"code": -32600, "message": "Invalid request"}}, 400)
        method_name = payload["method"]
        req_id = payload.get("id")
        if method_name == "notifications/initialized":
            return Response(None, status=202)
        if req_id is None or isinstance(req_id, bool) or not isinstance(req_id, (str, int)):
            return reply({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}, 400)
        def ok(value):
            return reply({"jsonrpc": "2.0", "id": req_id, "result": value})
        if method_name == "server/discover":
            return ok({"supportedVersions": [PROTOCOL], "capabilities": {"tools": {}}})
        if method_name == "initialize":
            return ok({"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                       "serverInfo": {"name": "ALDOL MAJUNG Cloudflare Candidate", "version": "0.1.0"}})
        if method_name == "tools/list":
            return ok({"tools": TOOL_SPECS})
        if method_name == "tools/call":
            params = payload.get("params")
            if not isinstance(params, dict):
                return reply({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "Invalid params"}}, 400)
            try:
                value = invoke_tool(params.get("name"), params.get("arguments", {}),
                    allow_live=getattr(self.env, "MAJUNG_LIVE_ENABLED", "false") == "true")
                return ok({"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}],
                           "structuredContent": value, "isError": False})
            except (ValueError, TypeError, KeyError, OverflowError, OSError) as exc:
                # Reject malformed inputs without revealing backend secrets or stack traces.
                safe = str(exc)[:200]
                return ok({"content": [{"type": "text", "text": safe}], "isError": True})
        return reply({"jsonrpc": "2.0", "id": req_id,
                      "error": {"code": -32601, "message": "Method not found"}}, 404)
