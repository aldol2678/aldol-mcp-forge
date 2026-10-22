"""HttpOnly session cookie. The MCP key is compared on the server and never stored in the cookie."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time

COOKIE = "aldol_mobile_session"
TTL_SECONDS = 30 * 60
_TOKEN = re.compile(r"v1\.(\d{1,10})\.([0-9a-f]{16})\.([0-9a-f]{64})\Z")


def configured() -> bool:
    return len(os.getenv("ALDOL_DESIGN_MCP_KEY", "")) >= 32


def _mac_key() -> bytes:
    key = os.getenv("ALDOL_DESIGN_MCP_KEY", "").encode("utf-8")
    return hashlib.sha256(b"aldol-mobile-session-v1\0" + key).digest()


def matches(provided: object) -> bool:
    """Compare a caller-supplied key without returning it or branching on its length."""
    expected = os.getenv("ALDOL_DESIGN_MCP_KEY", "")
    if len(expected) < 32 or not isinstance(provided, str) or not provided:
        return False
    provided_digest = hashlib.sha256(provided.encode("utf-8")).digest()
    expected_digest = hashlib.sha256(expected.encode("utf-8")).digest()
    return hmac.compare_digest(provided_digest, expected_digest)


def issue(now: int | None = None) -> str:
    if not configured():
        raise RuntimeError("service_not_configured")
    current = int(time.time() if now is None else now)
    expires = current + TTL_SECONDS
    nonce = secrets.token_hex(8)
    body = f"v1.{expires}.{nonce}"
    signature = hmac.new(_mac_key(), body.encode("ascii"), hashlib.sha256).hexdigest()
    return body + "." + signature


def valid(token: object, now: int | None = None) -> bool:
    if not configured() or not isinstance(token, str):
        return False
    match = _TOKEN.fullmatch(token)
    if match is None:
        return False
    expires = int(match.group(1))
    current = int(time.time() if now is None else now)
    if expires <= current or expires > current + TTL_SECONDS + 60:
        return False
    body = f"v1.{match.group(1)}.{match.group(2)}"
    expected = hmac.new(_mac_key(), body.encode("ascii"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, match.group(3))
