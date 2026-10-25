"""Single-owner OAuth resource server. An established IdP owns code/PKCE/login.

No local password form, authorization-code minting or token passthrough. Configuration
is operator-owned; incoming JWT headers can never select a network destination.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import os
import time
from urllib.parse import urlsplit

import httpx2
import jwt

SCOPE = "gameops:use"
ALGORITHMS = ("RS256", "ES256")


def https_url(value: str) -> str:
    p = urlsplit(value)
    if (p.scheme != "https" or not p.hostname or p.username or p.password
            or p.query or p.fragment or p.port not in (None, 443)):
        raise ValueError("OAuth URLs must be exact HTTPS URLs without credentials/query/fragment")
    # Also exclude characters unsafe in WWW-Authenticate.
    if any(ord(c) < 33 or ord(c) > 126 or c in '\\"' for c in value):
        raise ValueError("Invalid OAuth URL")
    return value


@dataclass(frozen=True)
class OAuthConfig:
    issuer: str
    resource: str
    owner_subject: str

    def __post_init__(self):
        https_url(self.issuer)
        https_url(self.resource)
        if urlsplit(self.resource).path != "/mcp":
            raise ValueError("OAuth resource must be the exact HTTPS /mcp endpoint")
        if not self.owner_subject or len(self.owner_subject) > 256:
            raise ValueError("An exact immutable OAuth owner subject is required")

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("GAME_OPS_OAUTH_ISSUER", ""),
                   os.environ.get("GAME_OPS_OAUTH_RESOURCE", ""),
                   os.environ.get("GAME_OPS_OAUTH_OWNER_SUB", ""))

    @property
    def metadata_url(self):
        p = urlsplit(self.resource)
        return f"{p.scheme}://{p.netloc}/.well-known/oauth-protected-resource/mcp"

    @property
    def challenge(self):
        return f'Bearer resource_metadata="{self.metadata_url}", scope="{SCOPE}"'

    def metadata(self):
        return {"resource": self.resource, "authorization_servers": [self.issuer],
                "scopes_supported": [SCOPE], "bearer_methods_supported": ["header"]}


class OAuthUnavailable(Exception):
    """Provider/configuration is unavailable; never fall back to unauthenticated access."""


class OAuthVerifier:
    def __init__(self, config: OAuthConfig, *, transport=None):
        self.config = config
        self.transport = transport  # Only supplied by local tests.
        self.keys = []
        self.expires = 0.0
        self.last_attempt = float("-inf")
        self.lock = asyncio.Lock()

    async def _json(self, client, url):
        async with client.stream("GET", url) as r:
            r.raise_for_status()  # Redirects are not followed.
            data = bytearray()
            async for chunk in r.aiter_bytes():
                data.extend(chunk)
                if len(data) > 128 * 1024:
                    raise ValueError("OAuth metadata size limit")
            value = json.loads(data)
            if not isinstance(value, dict):
                raise ValueError("Invalid OAuth metadata")
            return value

    async def refresh(self):
        async with self.lock:
            now = time.monotonic()
            # Bound unknown-kid spray and provider outage retries, including cold start.
            if now - self.last_attempt < 30:
                if now >= self.expires:
                    raise OAuthUnavailable("OAuth provider unavailable")
                return
            self.last_attempt = now
            try:
                async with httpx2.AsyncClient(timeout=5, follow_redirects=False,
                                             trust_env=False, transport=self.transport) as client:
                    p = urlsplit(self.config.issuer)
                    discovery = f"https://{p.netloc}/.well-known/oauth-authorization-server{p.path.rstrip('/')}"
                    try:
                        meta = await self._json(client, discovery)
                    except httpx2.HTTPStatusError as exc:
                        if exc.response.status_code != 404:
                            raise
                        meta = await self._json(client, self.config.issuer.rstrip('/') + "/.well-known/openid-configuration")
                    if meta.get("issuer") != self.config.issuer:
                        raise ValueError("Issuer mismatch")
                    if "S256" not in meta.get("code_challenge_methods_supported", []):
                        raise ValueError("Provider must advertise S256 PKCE")
                    if "code" not in meta.get("response_types_supported", []):
                        raise ValueError("Provider must support authorization code")
                    if "authorization_code" not in meta.get("grant_types_supported", ["authorization_code"]):
                        raise ValueError("Provider must support authorization code")
                    if SCOPE not in meta.get("scopes_supported", []):
                        raise ValueError("Provider must advertise gameops:use")
                    if not set(meta.get("token_endpoint_auth_methods_supported", [])).intersection(
                            {"none", "private_key_jwt", "client_secret_basic", "client_secret_post"}):
                        raise ValueError("Provider must advertise a supported token endpoint auth method")
                    for field in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
                        url = https_url(meta.get(field, ""))
                        if urlsplit(url).netloc != p.netloc:
                            raise ValueError("Provider endpoints must share configured issuer origin")
                    jwks = await self._json(client, meta["jwks_uri"])
                    keys = jwks.get("keys")
                    if not isinstance(keys, list) or not 1 <= len(keys) <= 32:
                        raise ValueError("Invalid JWKS")
                    self.keys = keys
                    self.expires = time.monotonic() + 300
            except (httpx2.HTTPError, ValueError, TypeError, KeyError) as exc:
                raise OAuthUnavailable("OAuth provider unavailable or incompatible") from exc

    async def verify(self, token: str) -> bool:
        if not isinstance(token, str) or len(token) > 16384:
            return False
        try:
            header = jwt.get_unverified_header(token)
            alg, kid = header.get("alg"), header.get("kid")
            if (alg not in ALGORITHMS or not isinstance(kid, str) or not 1 <= len(kid) <= 256
                    or any(k in header for k in ("jku", "jwk", "x5u", "crit"))):
                return False
            if time.monotonic() >= self.expires:
                await self.refresh()
            matches = [k for k in self.keys if isinstance(k, dict) and k.get("kid") == kid]
            if not matches:
                await self.refresh()
                matches = [k for k in self.keys if isinstance(k, dict) and k.get("kid") == kid]
            if len(matches) != 1:
                return False
            key = matches[0]
            if key.get("use", "sig") != "sig" or key.get("alg", alg) != alg:
                return False
            if "verify" not in key.get("key_ops", ["verify"]):
                return False
            claims = jwt.decode(token, jwt.PyJWK.from_dict(key, algorithm=alg).key,
                                algorithms=[alg], issuer=self.config.issuer,
                                audience=self.config.resource, subject=self.config.owner_subject,
                                options={"require": ["iss", "aud", "sub", "iat", "exp"],
                                         "strict_aud": True})
            scopes = claims.get("scope")
            if not isinstance(scopes, str) or SCOPE not in scopes.split():
                return False
            # Limit access-token exposure; IdP refresh tokens remain at the OAuth client.
            if not 0 < claims["exp"] - claims["iat"] <= 3600:
                return False
            return True
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            return False
