"""Local IdP fixtures are not evidence of a production OAuth login or Android use."""
import asyncio
import json
import time
from pathlib import Path
import sys

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx2
import jwt
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from oauth_resource import OAuthConfig, OAuthVerifier, OAuthUnavailable, SCOPE
from server import http_app
from service import QAService
from test_protocol import exercise, payload
from test_service import upload

ISSUER = "https://idp.example.test/tenant"
RESOURCE = "https://game-ops.example.test/mcp"
OWNER = "immutable-owner-id"
CONFIG = OAuthConfig(ISSUER, RESOURCE, OWNER)
LEGACY = "local-test-only-credential-0000000000000000"


@pytest.fixture
def idp():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    jwk.update(kid="key-1", alg="RS256", use="sig")
    meta = {"issuer": ISSUER, "authorization_endpoint": ISSUER + "/authorize",
            "token_endpoint": ISSUER + "/token", "jwks_uri": ISSUER + "/jwks",
            "code_challenge_methods_supported": ["S256"],
            "response_types_supported": ["code"], "grant_types_supported": ["authorization_code"],
            "scopes_supported": [SCOPE], "token_endpoint_auth_methods_supported": ["none"]}
    state = {"meta": meta, "keys": [jwk], "calls": []}

    def handler(request):
        state["calls"].append(str(request.url))
        if "failure" in state:
            return httpx2.Response(state["failure"])
        if str(request.url) == "https://idp.example.test/.well-known/oauth-authorization-server/tenant":
            return httpx2.Response(200, json=state["meta"])
        if str(request.url) == ISSUER + "/jwks":
            return httpx2.Response(200, json={"keys": state["keys"]})
        raise AssertionError("Unexpected URL: " + str(request.url))

    def token(changes=None, headers=None):
        now = int(time.time())
        claims = {"iss": ISSUER, "aud": RESOURCE, "sub": OWNER,
                  "iat": now, "exp": now + 600, "scope": SCOPE}
        claims.update(changes or {})
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "key-1", **(headers or {})})

    return state, token, OAuthVerifier(CONFIG, transport=httpx2.MockTransport(handler))


@pytest.mark.parametrize("changes", [
    {"iss": "https://attacker.test"}, {"aud": "another-api"}, {"aud": [RESOURCE, "another-api"]},
    {"sub": "another-user"}, {"exp": int(time.time()) - 1}, {"exp": None}, {"iat": None},
    {"nbf": int(time.time()) + 600}, {"scope": "other"}, {"scope": [SCOPE]},
    {"exp": int(time.time()) + 7200},
])
def test_reject_wrong_claims(idp, changes):
    _, token, verifier = idp
    assert asyncio.run(verifier.verify(token(changes))) is False


def test_signature_header_and_owner(idp):
    state, token, verifier = idp

    async def run():
        assert await verifier.verify(token())
        good = token()
        assert not await verifier.verify(good.rsplit(".", 1)[0] + "." + "A" * 342)
        assert not await verifier.verify(token(headers={"jku": "https://attacker.test/key"}))
        assert not await verifier.verify(token(headers={"kid": "unknown"}))
        assert not await verifier.verify("x" * 16385)
        assert not await verifier.verify(jwt.encode({"sub": OWNER}, "attacker" * 8, algorithm="HS256", headers={"kid": "key-1"}))
        assert len(state["calls"]) == 2  # Cached JWKS; unknown kid cannot cause network spray.
    asyncio.run(run())


@pytest.mark.parametrize("field,value", [
    ("issuer", ISSUER + "/wrong"), ("code_challenge_methods_supported", ["plain"]),
    ("response_types_supported", ["token"]), ("scopes_supported", []),
    ("token_endpoint_auth_methods_supported", []),
    ("jwks_uri", "https://attacker.test/jwks"), ("token_endpoint", "http://idp.example.test/token"),
])
def test_incompatible_provider_fails_closed(idp, field, value):
    state, token, verifier = idp
    state["meta"][field] = value
    with pytest.raises(OAuthUnavailable):
        asyncio.run(verifier.verify(token()))


def test_outage_and_rotation(idp):
    state, token, verifier = idp
    async def run():
        state["failure"] = 503
        with pytest.raises(OAuthUnavailable):
            await verifier.verify(token())
        with pytest.raises(OAuthUnavailable):
            await verifier.verify(token())
        assert len(state["calls"]) == 1
        del state["failure"]
        verifier.last_attempt = float("-inf")
        assert await verifier.verify(token())
        state["keys"] = [{**state["keys"][0], "kid": "key-2"}]
        verifier.last_attempt = float("-inf")
        assert await verifier.verify(token(headers={"kid": "key-2"}))
        assert not await verifier.verify(token())
    asyncio.run(run())


def test_oauth_http_sdk_and_security(tmp_path, idp):
    _, token, verifier = idp
    app = http_app(QAService(tmp_path / "artifacts", tmp_path / "reports", remote=True),
                   LEGACY, oauth=verifier, mode="oauth")

    async def run():
        async with app.app.router.lifespan_context(app.app):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://localhost:8000") as client:
                metadata = await client.get("/.well-known/oauth-protected-resource/mcp")
                assert metadata.status_code == 200 and metadata.json() == CONFIG.metadata()
                assert (await client.post("/.well-known/oauth-protected-resource/mcp")).status_code == 405
                for h in ({}, {"Authorization": "Bearer " + LEGACY}, {"Authorization": "Bearer " + token({"sub": "someone-else"})}):
                    r = await client.post("/mcp", headers=h)
                    assert r.status_code == 401 and r.headers["WWW-Authenticate"] == CONFIG.challenge
                client.headers["Authorization"] = "Bearer " + token()
                assert (await client.post("/mcp", headers={"Origin": "https://evil.test"})).status_code == 403
                assert (await client.post("/mcp", content="x" * (3 * 1024 * 1024 + 1))).status_code == 413
                async with streamable_http_client("http://localhost:8000/mcp", http_client=client) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        await exercise(session)
                        assert payload(await session.call_tool("run_game_scenarios", {
                            "artifact": upload(), "profile": {"scenarios": []}}))["status"] == "UNKNOWN"
                        listing = await session.list_tools()
                        assert all(t.meta["securitySchemes"] == [{"type": "oauth2", "scopes": [SCOPE]}] for t in listing.tools)
                # Inspect actual wire: SDK clients may discard vendor top-level fields.
                r = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 44, "method": "tools/list"},
                                      headers={"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-03-26"})
                assert r.status_code == 200
                assert all(t["securitySchemes"] == t["_meta"]["securitySchemes"] for t in r.json()["result"]["tools"])
    asyncio.run(run())


def test_dual_and_default_mode(tmp_path, idp):
    _, token, verifier = idp
    service = QAService(tmp_path / "a", tmp_path / "r", remote=True)
    async def run():
        for mode in ("bearer", "dual"):
            app = http_app(service, LEGACY, oauth=verifier, mode=mode)
            async with app.app.router.lifespan_context(app.app):
                async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://localhost:8000") as c:
                    assert (await c.get("/healthz")).json()["auth_mode"] == mode
                    assert (await c.post("/mcp", headers=[("Authorization", "Bearer " + LEGACY), ("Authorization", "wrong")])).status_code == 401
                    for secret in ([LEGACY] if mode == "bearer" else [LEGACY, token()]):
                        c.headers["Authorization"] = "Bearer " + secret
                        async with streamable_http_client("http://localhost:8000/mcp", http_client=c) as streams:
                            async with ClientSession(streams[0], streams[1]) as s:
                                await s.initialize()
                                assert len((await s.list_tools()).tools) == 9
                    c.headers.pop("Authorization")
                    if mode == "bearer":
                        assert (await c.get("/.well-known/oauth-protected-resource")).status_code == 401
    asyncio.run(run())


def test_configuration_fails_closed(tmp_path, monkeypatch):
    service = QAService(tmp_path / "a", tmp_path / "r", remote=True)
    for key in ("GAME_OPS_OAUTH_ISSUER", "GAME_OPS_OAUTH_RESOURCE", "GAME_OPS_OAUTH_OWNER_SUB"):
        monkeypatch.delenv(key, raising=False)
    for mode in ("dual", "oauth", "typo"):
        with pytest.raises(ValueError):
            http_app(service, LEGACY, mode=mode)
    for issuer in ("", "http://idp.example.test", "https://user:secret@idp.example.test", "https://idp.example.test?q=a"):
        with pytest.raises(ValueError):
            OAuthConfig(issuer, RESOURCE, OWNER)
    with pytest.raises(ValueError):
        OAuthConfig(ISSUER, RESOURCE, "")
