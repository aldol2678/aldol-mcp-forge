"""OAuth2.1 DCR / S256 PKCE / owner-consent tests, no real account secrets."""
import asyncio
import base64
import hashlib
import hmac
import os
import re
import secrets
import time
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import httpx2

from enterprise_mcps.owner_oauth import OwnerOAuth

HOST = "seum-mcp-api-production.up.railway.app"
ORIGIN = "https://" + HOST
CALLBACK = "https://chatgpt.com/connector_platform_oauth_redirect"
PASSWORD = "p" * 44
SIGNING = "k" * 70

class OAuthTests(unittest.TestCase):
    def _oauth(self):
        with patch.dict(os.environ, {
            "ALDOL_SEUM_OAUTH_OWNER_PASSWORD": PASSWORD,
            "ALDOL_SEUM_OAUTH_SIGNING_KEY": SIGNING,
        }, clear=True):
            return OwnerOAuth(HOST)

    async def _client(self, oauth):
        async def app(scope, receive, send):
            return await oauth.route(scope, receive, send)
        return httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url=ORIGIN,
            follow_redirects=False)

    def test_configuration_must_have_separate_strong_owner_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                OwnerOAuth(HOST)
        with patch.dict(os.environ, {
            "ALDOL_SEUM_OAUTH_OWNER_PASSWORD": "weak",
            "ALDOL_SEUM_OAUTH_SIGNING_KEY": SIGNING,
        }, clear=True):
            with self.assertRaises(RuntimeError):
                OwnerOAuth(HOST)

    def test_metadata_and_chatgpt_only_registration(self):
        async def verify():
            oauth = self._oauth()
            async with await self._client(oauth) as client:
                r = await client.get("/.well-known/oauth-protected-resource")
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.json()["resource"], ORIGIN)
                r = await client.get("/.well-known/oauth-authorization-server")
                self.assertEqual(r.status_code, 200)
                self.assertIn("S256", r.json()["code_challenge_methods_supported"])
                self.assertIn("refresh_token", r.json()["grant_types_supported"])
                bad = await client.post("/oauth/register", json={
                    "redirect_uris": ["https://attacker.example/callback"]})
                self.assertEqual(bad.status_code, 400)
                ok = await client.post("/oauth/register",
                                       json={"redirect_uris": [CALLBACK],
                                             "token_endpoint_auth_method": "none"})
                self.assertEqual(ok.status_code, 201)
                self.assertEqual(ok.json()["client_id"], oauth.client_id(CALLBACK))
                self.assertEqual(ok.json()["redirect_uris"], [CALLBACK])
        asyncio.run(verify())

    def test_owner_consent_pkce_replay_denial_refresh_rotation_and_scope(self):
        async def verify():
            oauth = self._oauth()
            async with await self._client(oauth) as client:
                verifier = secrets.token_urlsafe(48)
                challenge = base64.urlsafe_b64encode(
                    hashlib.sha256(verifier.encode()).digest()
                ).rstrip(b"=").decode()
                params = {
                    "response_type": "code", "client_id": oauth.client_id(CALLBACK),
                    "redirect_uri": CALLBACK, "code_challenge": challenge,
                    "code_challenge_method": "S256", "resource": ORIGIN,
                    "scope": "seum:read offline_access",
                    "state": secrets.token_urlsafe(32),
                }
                auth = await client.get("/oauth/authorize", params=params)
                self.assertEqual(auth.status_code, 200)
                self.assertIn("소유자 승인 암호", auth.text)
                nonce = re.search('name="nonce" value="([^"]+)"', auth.text).group(1)
                csrf = re.search('name="csrf" value="([^"]+)"', auth.text).group(1)
                invalid = await client.post("/oauth/approve", data={
                    "nonce": nonce, "csrf": csrf, "password": "incorrect"},
                    headers={"Origin": ORIGIN})
                self.assertEqual(invalid.status_code, 403)
                no_origin = await client.post("/oauth/approve", data={
                    "nonce": nonce, "csrf": csrf, "password": PASSWORD})
                self.assertEqual(no_origin.status_code, 403)
                accepted = await client.post("/oauth/approve", data={
                    "nonce": nonce, "csrf": csrf, "password": PASSWORD},
                    headers={"Origin": ORIGIN})
                self.assertEqual(accepted.status_code, 303)
                location = accepted.headers["location"]
                self.assertTrue(location.startswith(CALLBACK))
                code = parse_qs(urlparse(location).query)["code"][0]
                self.assertEqual(parse_qs(urlparse(location).query)["state"][0],
                                 params["state"])
                body = {"grant_type": "authorization_code", "client_id": params["client_id"],
                        "redirect_uri": CALLBACK, "code": code, "code_verifier": verifier,
                        "resource": ORIGIN}
                redeemed = await client.post("/oauth/token", data=body)
                self.assertEqual(redeemed.status_code, 200, redeemed.text)
                tokens = redeemed.json()
                self.assertTrue(oauth.authorized(("Bearer " + tokens["access_token"]).encode()))
                self.assertFalse(oauth.authorized(b"Bearer attacker"))
                replay = await client.post("/oauth/token", data=body)
                self.assertEqual(replay.status_code, 400)
                rotated = await client.post("/oauth/token", data={
                    "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"],
                    "client_id": params["client_id"], "resource": ORIGIN})
                self.assertEqual(rotated.status_code, 200)
                self.assertNotEqual(rotated.json()["refresh_token"], tokens["refresh_token"])
                reused = await client.post("/oauth/token", data={
                    "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"],
                    "client_id": params["client_id"], "resource": ORIGIN})
                self.assertEqual(reused.status_code, 400)
                self.assertTrue(oauth.authorized(("Bearer " + rotated.json()["access_token"]).encode()))
        asyncio.run(verify())

    def test_rejects_unsafe_code_challenge_wrong_resource_and_client(self):
        async def verify():
            oauth = self._oauth()
            async with await self._client(oauth) as client:
                base = {"response_type": "code", "client_id": oauth.client_id(CALLBACK),
                        "redirect_uri": CALLBACK, "code_challenge": "a" * 43,
                        "code_challenge_method": "S256",
                        "resource": ORIGIN, "scope": "seum:read", "state": "xyz" * 12}
                for change in ({"redirect_uri": "https://evil.example"},
                               {"client_id": "forged"},
                               {"code_challenge_method": "plain"},
                               {"scope": "seum:write"},
                               {"resource": "https://other.example"}):
                    r = await client.get("/oauth/authorize", params={**base, **change})
                    self.assertEqual(r.status_code, 400, change)
        asyncio.run(verify())

    def test_bearer_integrates_existing_http_server_and_denies_unauthenticated(self):
        async def verify():
            with patch.dict(os.environ, {
                "ALDOL_SEUM_MCP_BEARER_TOKEN": "b" * 50,
                "ALDOL_SEUM_OAUTH_OWNER_PASSWORD": PASSWORD,
                "ALDOL_SEUM_OAUTH_SIGNING_KEY": SIGNING,
                "ALDOL_SEUM_OAUTH_ENABLED": "1",
                "ALDOL_SEUM_PUBLIC_HOST": HOST,
                "ALDOL_SEUM_GITHUB_READ_ENABLED": "0",
                "ALDOL_SEUM_STARTUP_PROBE_ENABLED": "0",
            }, clear=True):
                from enterprise_mcps.http_server import create_http_app
                app = create_http_app()
                async with httpx2.AsyncClient(
                    transport=httpx2.ASGITransport(app=app),
                    base_url=ORIGIN, follow_redirects=False) as client:
                    anon = await client.get("/mcp")
                    self.assertEqual(anon.status_code, 401)
                    self.assertIn("resource_metadata=", anon.headers["www-authenticate"])
                    metadata = await client.get("/.well-known/oauth-protected-resource")
                    self.assertEqual(metadata.status_code, 200)
                    fixed = await client.get("/status", headers={
                        "Authorization": "Bearer " + "b" * 50})
                    self.assertEqual(fixed.status_code, 200)
                    self.assertTrue(fixed.json()["oauth_enabled"])
                    fake = await client.get("/status", headers={
                        "Authorization": "Bearer wrong"})
                    self.assertEqual(fake.status_code, 401)
                    token = app.oauth._new_tokens(app.oauth.client_id(CALLBACK), "seum:read", ORIGIN).body
                    access = __import__("json").loads(token)["access_token"]
                    real = await client.get("/status", headers={
                        "Authorization": "Bearer " + access})
                    self.assertEqual(real.status_code, 200)
        asyncio.run(verify())

if __name__ == "__main__":
    unittest.main(verbosity=2)
