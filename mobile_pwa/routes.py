"""Mobile PWA routes. Static files contain no credential. API calls require the session cookie."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from mobile_pwa import auth, gateway

router = APIRouter()
STATIC = Path(__file__).resolve().parent / "static"
_FILES = {
    "index.html": "text/html; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "styles.css": "text/css; charset=utf-8",
    "manifest.webmanifest": "application/manifest+json",
    "sw.js": "text/javascript; charset=utf-8",
    "icon-192.png": "image/png",
    "icon-512.png": "image/png",
}
_PAGE_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self'; connect-src 'self'; worker-src 'self'; manifest-src 'self'; "
    "frame-src about:; object-src 'none'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)


def _origin_allowed(request: Request) -> bool:
    site = request.headers.get("sec-fetch-site")
    if site and site not in ("same-origin", "none"):
        return False
    origin = request.headers.get("origin")
    if not origin:
        return True
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    forwarded_host = request.headers.get("x-forwarded-host", request.headers.get("host", "")).split(",")[0].strip()
    expected = {f"{forwarded_proto}://{forwarded_host}", f"{request.url.scheme}://{request.url.netloc}"}
    return origin in expected


def _secure(request: Request) -> bool:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    return proto == "https"


async def _body(request: Request, limit: int) -> dict:
    raw_length = request.headers.get("content-length")
    if raw_length is not None:
        try:
            length = int(raw_length)
        except ValueError:
            raise gateway.FlowError("request", "invalid_json")
        if length > limit:
            raise gateway.FlowError("request", "body_too_large")
    payload = await request.body()
    if len(payload) > limit:
        raise gateway.FlowError("request", "body_too_large")
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, UnicodeError):
        raise gateway.FlowError("request", "invalid_json") from None
    if not isinstance(data, dict):
        raise gateway.FlowError("request", "invalid_json")
    return data


def _reject(status: int, error: str, step: str | None = None, message: str | None = None) -> JSONResponse:
    body = {"error": error}
    if step:
        body["step"] = step
    if message and message != error:
        body["message"] = message
    return JSONResponse(body, status_code=status)


def _file(name: str) -> Response:
    response = FileResponse(STATIC / name, media_type=_FILES[name])
    if name == "index.html":
        response.headers["Content-Security-Policy"] = _PAGE_CSP
    return response


def _authenticated(request: Request) -> bool:
    return auth.valid(request.cookies.get(auth.COOKIE))


@router.get("/mobile", include_in_schema=False)
async def mobile_redirect() -> RedirectResponse:
    return RedirectResponse("/mobile/", status_code=307)


@router.get("/mobile/", include_in_schema=False)
async def mobile_index() -> Response:
    return _file("index.html")


@router.get("/mobile/{asset}", include_in_schema=False)
async def mobile_asset(asset: str) -> Response:
    if asset not in _FILES or asset == "index.html":
        return JSONResponse({"error": "not_found"}, status_code=404)
    return _file(asset)


@router.get("/mobile/api/session")
async def session_status(request: Request) -> JSONResponse:
    if not _origin_allowed(request):
        return _reject(403, "origin_not_allowed")
    return JSONResponse({
        "configured": auth.configured(),
        "authenticated": _authenticated(request),
    })


@router.post("/mobile/api/session")
async def session_login(request: Request) -> JSONResponse:
    if not _origin_allowed(request):
        return _reject(403, "origin_not_allowed")
    if not auth.configured():
        return _reject(503, "service_not_configured")
    try:
        data = await _body(request, 2048)
    except gateway.FlowError as exc:
        status = 413 if exc.message == "body_too_large" else 400
        return _reject(status, exc.message)
    if set(data) - {"key"}:
        return _reject(400, "invalid_json")
    provided = data.get("key")
    if not auth.matches(provided):
        return _reject(401, "unauthorized")
    response = JSONResponse({"ok": True})
    response.set_cookie(
        auth.COOKIE,
        auth.issue(),
        max_age=auth.TTL_SECONDS,
        httponly=True,
        secure=_secure(request),
        samesite="strict",
        path="/mobile",
    )
    return response


@router.delete("/mobile/api/session")
async def session_logout(request: Request) -> JSONResponse:
    if not _origin_allowed(request):
        return _reject(403, "origin_not_allowed")
    response = JSONResponse({"ok": True, "authenticated": False})
    response.delete_cookie(auth.COOKIE, path="/mobile", samesite="strict", secure=_secure(request))
    return response


@router.get("/mobile/api/tools")
async def tools(request: Request) -> JSONResponse:
    if not _origin_allowed(request):
        return _reject(403, "origin_not_allowed")
    if not auth.configured():
        return _reject(503, "service_not_configured")
    if not _authenticated(request):
        return _reject(401, "unauthorized")
    return JSONResponse(await gateway.list_catalog())


@router.post("/mobile/api/flow")
async def flow(request: Request) -> JSONResponse:
    if not _origin_allowed(request):
        return _reject(403, "origin_not_allowed")
    if not auth.configured():
        return _reject(503, "service_not_configured")
    if not _authenticated(request):
        return _reject(401, "unauthorized")
    try:
        data = await _body(request, 32_000)
        result = await gateway.run_flow(data)
    except gateway.FlowError as exc:
        if exc.message == "body_too_large":
            return _reject(413, "body_too_large", exc.step)
        if exc.message == "invalid_json":
            return _reject(400, "invalid_json", exc.step)
        return _reject(422, "tool_rejected", exc.step, exc.message)
    except Exception:
        return _reject(500, "tool_failed")
    return JSONResponse(result)
