"""Owner-approved OAuth 2.1 + PKCE for private SEUM MCP connections.

Single owner/single instance: DCR public clients are constrained to ChatGPT
callbacks; owner approval requires a separate login passphrase. Codes and
tokens are opaque, in-memory and discarded on restart (reconnection required).
No credentials are embedded in plugins or responses.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import time
from urllib.parse import urlencode

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

CALLBACK = re.compile(
    r"^https://chatgpt\.com/(?:connector_platform_oauth_redirect|connector/oauth/[A-Za-z0-9_-]{8,128})$")
CHALLENGE = re.compile(r"^[A-Za-z0-9_-]{43,128}$")
NO_CACHE = {"Cache-Control": "no-store", "Pragma": "no-cache"}
ACCESS_LIFETIME = 1800
REFRESH_LIFETIME = 7 * 86400
PAGE_LIFETIME = 300
CODE_LIFETIME = 90


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _string(value, maximum=2048) -> bool:
    return isinstance(value, str) and 0 < len(value) <= maximum


class OwnerOAuth:
    def __init__(self, host: str):
        self.issuer = "https://" + host
        self.resource = self.issuer
        password = os.environ.get("ALDOL_SEUM_OAUTH_OWNER_PASSWORD", "")
        signing = os.environ.get("ALDOL_SEUM_OAUTH_SIGNING_KEY", "")
        if (len(password) < 32 or len(password) > 256
                or len(signing) < 48 or len(signing) > 256
                or not password.isascii() or not signing.isascii()):
            raise RuntimeError("OAuth owner password (32+) and persistent signing key (48+) required")
        self.password = password.encode("ascii")
        self.key = signing.encode("ascii")
        self.pages = {}
        self.codes = {}
        self.access = {}
        self.refresh = {}
        self.attempts = {}

    def client_id(self, callback: str) -> str:
        return "seum_" + _b64(hmac.digest(self.key, ("client:" + callback).encode(), "sha256"))

    def _prune(self) -> None:
        now = time.time()
        for bucket in (self.pages, self.codes, self.access, self.refresh):
            for k, v in list(bucket.items()):
                if v["exp"] < now:
                    bucket.pop(k, None)

    def _error(self, message: str, status=400):
        return JSONResponse({"error": message}, status_code=status, headers=NO_CACHE)

    def _validate_callback(self, callback: str) -> bool:
        return isinstance(callback, str) and CALLBACK.fullmatch(callback) is not None

    def metadata(self, path: str):
        if path == "/.well-known/oauth-protected-resource":
            return JSONResponse({
                "resource": self.resource,
                "authorization_servers": [self.issuer],
                "scopes_supported": ["seum:read"]
            }, headers=NO_CACHE)
        return JSONResponse({
            "issuer": self.issuer,
            "authorization_endpoint": self.issuer + "/oauth/authorize",
            "token_endpoint": self.issuer + "/oauth/token",
            "registration_endpoint": self.issuer + "/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["none"],
            "code_challenge_methods_supported": ["S256"],
            "scopes_supported": ["seum:read", "offline_access"],
            "client_id_metadata_document_supported": False,
        }, headers=NO_CACHE)

    async def register(self, request: Request):
        self._prune()
        try:
            body = await request.json()
        except Exception:
            return self._error("invalid_client_metadata")
        if not isinstance(body, dict):
            return self._error("invalid_client_metadata")
        redirects = body.get("redirect_uris")
        if not isinstance(redirects, list) or len(redirects) != 1 or not self._validate_callback(redirects[0]):
            return self._error("invalid_redirect_uri")
        if body.get("token_endpoint_auth_method", "none") != "none":
            return self._error("unsupported_client_auth_method")
        if body.get("grant_types", ["authorization_code", "refresh_token"]) not in (
                ["authorization_code"], ["authorization_code", "refresh_token"]):
            return self._error("unsupported_grant_types")
        callback = redirects[0]
        return JSONResponse({
            "client_id": self.client_id(callback),
            "client_id_issued_at": int(time.time()),
            "redirect_uris": [callback],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "client_name": "ALDOL SEUM (private owner)"
        }, status_code=201, headers=NO_CACHE)

    def _validate_auth_request(self, query):
        callback = query.get("redirect_uri")
        client = query.get("client_id")
        challenge = query.get("code_challenge")
        method = query.get("code_challenge_method")
        state = query.get("state")
        resource = query.get("resource")
        scopes = set(query.get("scope", "").split())
        if not self._validate_callback(callback):
            return None
        if not _string(client, 200) or not hmac.compare_digest(client, self.client_id(callback)):
            return None
        if (query.get("response_type") != "code" or method != "S256"
                or not isinstance(challenge, str) or not CHALLENGE.fullmatch(challenge)):
            return None
        if not _string(state, 2000) or len(state) < 10:
            return None
        if resource != self.resource or not scopes or not scopes.issubset({"seum:read", "offline_access"}) or "seum:read" not in scopes:
            return None
        return {"redirect": callback, "client": client, "challenge": challenge,
                "state": state, "resource": resource, "scope": " ".join(sorted(scopes))}

    async def authorize(self, request: Request):
        self._prune()
        params = self._validate_auth_request(request.query_params)
        if params is None:
            return self._error("invalid_authorization_request")
        nonce = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        self.pages[_digest(nonce)] = {**params, "csrf_hash": _digest(csrf),
                                     "exp": time.time() + PAGE_LIFETIME}
        page = """<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ALDOL SEUM 연결 승인</title><body>
<main style="max-width:440px;margin:8vh auto;font:16px system-ui;line-height:1.5">
<h1>ALDOL SEUM 연결 승인</h1>
<p>ChatGPT에 코드 정적 분석 등 세움 읽기 도구 3개의 사용을 허용합니다.
GitHub 수정, PR 병합, 배포 권한은 제공하지 않습니다.</p>
<form method="post" action="/oauth/approve" autocomplete="off">
<input type="hidden" name="nonce" value="%s">
<input type="hidden" name="csrf" value="%s">
<label for="secret">소유자 승인 암호</label>
<input id="secret" name="password" type="password" required
autocomplete="off" style="width:100%%;padding:10px">
<button type="submit" style="padding:10px;margin-top:16px">연결 승인</button>
</form><p><small>이 암호는 ChatGPT 대화에 입력하지 마세요.</small></p>
</main></body></html>""" % (html.escape(nonce, quote=True),
                               html.escape(csrf, quote=True))
        response = HTMLResponse(page, headers={
            **NO_CACHE, "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
            "Referrer-Policy": "no-referrer"
        })
        response.set_cookie("seum_oauth_nonce", nonce, max_age=PAGE_LIFETIME,
                            secure=True, httponly=True, samesite="lax",
                            path="/oauth")
        return response

    async def approve(self, request: Request):
        if request.headers.get("origin") != self.issuer:
            return self._error("invalid_origin", 403)
        self._prune()
        try:
            form = await request.form()
        except Exception:
            return self._error("invalid_form")
        nonce = form.get("nonce")
        csrf = form.get("csrf")
        password = form.get("password")
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        strikes = [t for t in self.attempts.get(ip, []) if t + 600 > now]
        if len(strikes) >= 6:
            return self._error("approval_rate_limited", 429)
        if (not _string(nonce, 64) or not _string(csrf, 64)
                or request.cookies.get("seum_oauth_nonce") != nonce):
            return self._error("invalid_session", 403)
        entry = self.pages.get(_digest(nonce))
        if not entry or not hmac.compare_digest(entry["csrf_hash"], _digest(csrf)):
            return self._error("expired_or_invalid_session", 403)
        if (not isinstance(password, str) or len(password) > 256
                or not hmac.compare_digest(password.encode("utf-8"), self.password)):
            strikes.append(now)
            self.attempts[ip] = strikes
            return self._error("approval_rejected", 403)
        self.pages.pop(_digest(nonce), None)
        code = secrets.token_urlsafe(36)
        self.codes[_digest(code)] = {**entry, "exp": now + CODE_LIFETIME}
        location = entry["redirect"] + "?" + urlencode(
            {"code": code, "state": entry["state"]})
        response = RedirectResponse(location, status_code=303, headers=NO_CACHE)
        response.delete_cookie("seum_oauth_nonce", path="/oauth")
        return response

    def _new_tokens(self, client, scope, resource):
        access = secrets.token_urlsafe(42)
        refresh = secrets.token_urlsafe(48)
        self.access[_digest(access)] = {"exp": time.time() + ACCESS_LIFETIME,
                                       "client": client, "scope": scope, "resource": resource}
        self.refresh[_digest(refresh)] = {"exp": time.time() + REFRESH_LIFETIME,
                                         "client": client, "scope": scope, "resource": resource}
        return JSONResponse({"access_token": access, "token_type": "Bearer",
                             "expires_in": ACCESS_LIFETIME, "refresh_token": refresh,
                             "scope": scope}, headers=NO_CACHE)

    async def token(self, request: Request):
        self._prune()
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/x-www-form-urlencoded":
            return self._error("invalid_request")
        try:
            form = await request.form()
        except Exception:
            return self._error("invalid_request")
        grant = form.get("grant_type")
        client = form.get("client_id")
        resource = form.get("resource")
        if not isinstance(client, str) or resource != self.resource:
            return self._error("invalid_client", 401)
        if grant == "authorization_code":
            code = form.get("code")
            verifier = form.get("code_verifier")
            redirect = form.get("redirect_uri")
            if not _string(code, 128) or not _string(verifier, 128):
                return self._error("invalid_grant")
            entry = self.codes.pop(_digest(code), None)
            if (not entry or entry["client"] != client or entry["redirect"] != redirect):
                return self._error("invalid_grant")
            calc = _b64(hashlib.sha256(verifier.encode("ascii", errors="ignore")).digest())
            if not hmac.compare_digest(entry["challenge"], calc):
                return self._error("invalid_grant")
            return self._new_tokens(client, entry["scope"], resource)
        if grant == "refresh_token":
            opaque = form.get("refresh_token")
            if not _string(opaque, 200):
                return self._error("invalid_grant")
            entry = self.refresh.pop(_digest(opaque), None)
            if not entry or entry["client"] != client or entry["resource"] != resource:
                return self._error("invalid_grant")
            return self._new_tokens(client, entry["scope"], resource)
        return self._error("unsupported_grant_type")

    def authorized(self, bearer: bytes) -> bool:
        if not bearer.startswith(b"Bearer "):
            return False
        try:
            token = bearer[7:].decode("ascii")
        except UnicodeError:
            return False
        entry = self.access.get(_digest(token))
        return bool(entry and entry["exp"] > time.time()
                    and entry["resource"] == self.resource
                    and "seum:read" in entry["scope"].split())

    async def route(self, scope, receive, send):
        req = Request(scope, receive)
        path, method = scope["path"], scope["method"]
        if path in ("/.well-known/oauth-protected-resource",
                    "/.well-known/oauth-authorization-server") and method == "GET":
            response = self.metadata(path)
        elif path == "/oauth/register" and method == "POST":
            response = await self.register(req)
        elif path == "/oauth/authorize" and method == "GET":
            response = await self.authorize(req)
        elif path == "/oauth/approve" and method == "POST":
            response = await self.approve(req)
        elif path == "/oauth/token" and method == "POST":
            response = await self.token(req)
        else:
            response = self._error("not_found", 404)
        return await response(scope, receive, send)
