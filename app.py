"""Vercel-only isolated design MCP preview. Two bounded, authenticated MCP mounts.

No Railway dependency. No database, filesystem changes, arbitrary code execution
or remote fetches. Session managers are started by the parent ASGI lifespan.
"""
from __future__ import annotations

import hmac
import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

sys.path.insert(0, str(Path(__file__).resolve().parent / "packages" / "ui-mcp"))
from ui_core.server import app as ui_mcp
from enterprise_mcps import bonsae
from enterprise_mcps.common import verify_output

bonsae_mcp = MCPServer("aldol-bonsae-mcp")

@bonsae_mcp.tool()
def analyze_design(reference: str, target: str | None = None) -> dict[str, str]:
    """Analyze supplied HTML/CSS. Does not fetch or execute remote content."""
    return verify_output("bonsae", "analyze_design", bonsae.analyze_design(reference, target))

@bonsae_mcp.tool()
def generate_design_spec(brief: str) -> dict[str, str]:
    """Draft component/state/responsive handoff, not a release approval."""
    return verify_output("bonsae", "generate_design_spec", bonsae.generate_design_spec(brief))

@bonsae_mcp.tool()
def review_visual(artifact: str) -> dict[str, str]:
    """Bounded pixel/source checks; incomplete visual evidence is never PASS."""
    return verify_output("bonsae", "review_visual", bonsae.review_visual(artifact))

def _security():
    hosts = ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"]
    for item in (os.getenv("VERCEL_URL"), os.getenv("VERCEL_PROJECT_PRODUCTION_URL")):
        if item and "/" not in item and ":" not in item and len(item) <= 254:
            hosts.extend([item, item + ":*"])
    custom = os.getenv("ALDOL_DESIGN_MCP_ALLOWED_HOST")
    if custom and "/" not in custom and ":" not in custom and len(custom) <= 254:
        hosts.extend([custom, custom + ":*"])
    return TransportSecuritySettings(
        allowed_hosts=hosts,
        allowed_origins=["https://chatgpt.com", "https://chat.openai.com"],
    )

security = _security()
ui_asgi = ui_mcp.streamable_http_app(
    json_response=True, stateless_http=True, max_request_body_size=3_000_000,
    transport_security=security,
)
bonsae_asgi = bonsae_mcp.streamable_http_app(
    json_response=True, stateless_http=True, max_request_body_size=3_000_000,
    transport_security=security,
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(ui_mcp.session_manager.run())
        await stack.enter_async_context(bonsae_mcp.session_manager.run())
        yield

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

@app.middleware("http")
async def bearer_auth(request: Request, call_next):
    if request.url.path == "/health" and request.method == "GET":
        return JSONResponse({"status": "ok", "service": "aldol-design-mcp-preview"})
    key = os.getenv("ALDOL_DESIGN_MCP_KEY", "")
    if len(key) < 32:
        return JSONResponse({"error": "service_not_configured"}, status_code=503)
    if request.url.path not in ("/ui/mcp", "/bonsae/mcp"):
        return JSONResponse({"error": "not_found"}, status_code=404)
    origin = request.headers.get("origin")
    if origin and origin not in ("https://chatgpt.com", "https://chat.openai.com"):
        return JSONResponse({"error": "origin_not_allowed"}, status_code=403)
    try:
        length = int(request.headers.get("content-length", "0"))
    except ValueError:
        return JSONResponse({"error": "invalid_content_length"}, status_code=400)
    if length > 3_000_000:
        return JSONResponse({"error": "body_too_large"}, status_code=413)
    if not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + key):
        return JSONResponse({"error": "unauthorized"}, status_code=401,
                            headers={"WWW-Authenticate": "Bearer",
                                     "Cache-Control": "no-store"})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response

app.mount("/ui", ui_asgi)
app.mount("/bonsae", bonsae_asgi)
