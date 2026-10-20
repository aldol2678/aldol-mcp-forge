"""Opt-in, bounded GitHub REST file read for SEUM static analysis.

This is NOT the ChatGPT GitHub connector and it does not receive connector
credentials. It reads only GitHub.com individual files, no writes, redirects,
user-controlled hosts, submodules, giant files, or executable code.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .common import safe_path, string

SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./-]{0,127}$")
BLOB_SHA = re.compile(r"^[0-9a-f]{40}$")
MAX_FILE_BYTES = 3500
MAX_API_BYTES = 16000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _locator(data: dict) -> tuple[str, str, str, str]:
    if set(data) != {"source", "owner", "repo", "path", "ref"}:
        raise ValueError("GitHub locator must contain source, owner, repo, path, ref")
    if data.get("source") != "github":
        raise ValueError("source must be github")
    owner = string(data.get("owner"), "owner", max_length=100)
    repo = string(data.get("repo"), "repo", max_length=100)
    if not SLUG.fullmatch(owner) or not SLUG.fullmatch(repo) or repo in (".", ".."):
        raise ValueError("Unsafe GitHub owner or repository identifier")
    path = safe_path(data.get("path"))
    if any(segment in (".", "..", "") for segment in path.split("/")):
        raise ValueError("Unsafe GitHub file path")
    ref = string(data.get("ref"), "ref", max_length=128)
    if (not REF.fullmatch(ref) or ref.startswith(".") or ref.endswith("/")
            or "//" in ref or ".." in ref or ref.endswith(".lock")):
        raise ValueError("Unsafe GitHub ref")
    return owner, repo, path, ref


def read_file(locator: dict) -> dict:
    owner, repo, path, ref = _locator(locator)
    if os.environ.get("ALDOL_SEUM_GITHUB_READ_ENABLED") != "1":
        raise ValueError("GITHUB_READ_DISABLED: explicitly opt in before remote GitHub reads")
    token = os.environ.get("ALDOL_SEUM_GITHUB_TOKEN", "")
    if token and (not token.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in token)
                  or len(token) > 300):
        raise ValueError("GitHub credential format rejected")
    # All requests are constructed internally against this *fixed* HTTPS API.
    # Path/ref input may never supply a scheme, hostname, redirect or query.
    encoded_path = "/".join(urllib.parse.quote(x, safe="") for x in path.split("/"))
    url = ("https://api.github.com/repos/"
           + urllib.parse.quote(owner, safe="") + "/"
           + urllib.parse.quote(repo, safe="") + "/contents/"
           + encoded_path + "?" + urllib.parse.urlencode({"ref": ref}))
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ALDOL-SEUM-MCP-readonly/0.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers, method="GET")
    # Refuse environment-proxy credential forwarding and redirected destinations.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=6) as response:
            if response.status != 200:
                raise ValueError("GitHub GET returned unexpected HTTP status")
            mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if mime not in ("application/json", "application/vnd.github+json"):
                raise ValueError("GitHub GET returned non-JSON content")
            raw = response.read(MAX_API_BYTES + 1)
    except urllib.error.HTTPError as exc:
        # No response headers or token in errors. 301/302/307/308 also refused.
        if exc.code in (301, 302, 303, 307, 308):
            raise ValueError("GitHub redirect refused") from None
        if exc.code in (401, 403):
            raise ValueError("GitHub read not authorized or rate limited") from None
        if exc.code == 404:
            raise ValueError("GitHub file missing or inaccessible") from None
        raise ValueError("GitHub request failed (HTTP " + str(exc.code) + ")") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ValueError("GitHub read failed (network unavailable)") from None
    if len(raw) > MAX_API_BYTES:
        raise ValueError("GitHub response exceeds bounded size limit")
    try:
        doc = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("GitHub returned invalid JSON metadata") from exc
    if not isinstance(doc, dict) or doc.get("type") != "file" or doc.get("encoding") != "base64":
        raise ValueError("GitHub entry is not an inline text file")
    size = doc.get("size")
    blob_sha = doc.get("sha")
    if (type(size) is not int or size < 0 or size > MAX_FILE_BYTES
            or not isinstance(blob_sha, str) or not BLOB_SHA.fullmatch(blob_sha)):
        raise ValueError("GitHub file size or blob SHA rejected")
    encoded = doc.get("content")
    if not isinstance(encoded, str):
        raise ValueError("GitHub file content not inline base64")
    try:
        content = base64.b64decode("".join(encoded.split()), validate=True)
        text = content.decode("utf-8", errors="strict")
    except (binascii.Error, UnicodeError) as exc:
        raise ValueError("GitHub file is not valid UTF-8 text") from exc
    if len(content) != size or len(content) > MAX_FILE_BYTES or len(text) > MAX_FILE_BYTES:
        raise ValueError("GitHub file length/size mismatch")
    # Git blob SHA verifies the API content against its declared Git object.
    calc_blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
    if calc_blob != blob_sha:
        raise ValueError("GITHUB_BLOB_INTEGRITY_FAILED: returned content did not match Git blob SHA")
    return {
        "path": path, "content": text, "git_blob_sha": blob_sha,
        "sha256": hashlib.sha256(content).hexdigest(),
        "source": "github", "owner": owner, "repo": repo, "ref": ref,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_url": ("https://github.com/" + owner + "/" + repo + "/blob/"
                       + urllib.parse.quote(ref, safe="/") + "/"
                       + "/".join(urllib.parse.quote(x, safe="") for x in path.split("/"))),
        "fetch_scope": "single-file-read-only",
        "credentialed": bool(token),
    }
