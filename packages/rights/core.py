"""ALDOL RIGHTS v0.1: evidence-first asset rights preflight, not legal clearance."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

VERSION = "0.1.0"
KINDS = frozenset({"image", "audio", "video", "font", "3d", "code", "text", "other"})

# Simplified flag checks. No policy inference from a URL or the name of a license.
LICENSES: dict[str, dict[str, Any]] = {
    "CC0-1.0": {"label": "CC0 1.0 Universal", "commercial": True, "adapt": True, "distribute": True, "attribution": False, "share_alike": False, "url": "https://creativecommons.org/publicdomain/zero/1.0/"},
    "CC-BY-4.0": {"label": "CC BY 4.0", "commercial": True, "adapt": True, "distribute": True, "attribution": True, "share_alike": False, "url": "https://creativecommons.org/licenses/by/4.0/"},
    "CC-BY-SA-4.0": {"label": "CC BY-SA 4.0", "commercial": True, "adapt": True, "distribute": True, "attribution": True, "share_alike": True, "url": "https://creativecommons.org/licenses/by-sa/4.0/"},
    "CC-BY-ND-4.0": {"label": "CC BY-ND 4.0", "commercial": True, "adapt": False, "distribute": True, "attribution": True, "share_alike": False, "url": "https://creativecommons.org/licenses/by-nd/4.0/"},
    "CC-BY-NC-4.0": {"label": "CC BY-NC 4.0", "commercial": False, "adapt": True, "distribute": True, "attribution": True, "share_alike": False, "url": "https://creativecommons.org/licenses/by-nc/4.0/"},
    "CC-BY-NC-SA-4.0": {"label": "CC BY-NC-SA 4.0", "commercial": False, "adapt": True, "distribute": True, "attribution": True, "share_alike": True, "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/"},
    "CC-BY-NC-ND-4.0": {"label": "CC BY-NC-ND 4.0", "commercial": False, "adapt": False, "distribute": True, "attribution": True, "share_alike": False, "url": "https://creativecommons.org/licenses/by-nc-nd/4.0/"},
    "MIT": {"label": "MIT License (manual notice review)", "commercial": None, "adapt": None, "distribute": None, "attribution": None, "share_alike": None, "url": "https://opensource.org/license/mit"},
    "APACHE-2.0": {"label": "Apache 2.0 (manual notice/patent review)", "commercial": None, "adapt": None, "distribute": None, "attribution": None, "share_alike": None, "url": "https://www.apache.org/licenses/LICENSE-2.0"},
    "OFL-1.1": {"label": "SIL Open Font License 1.1 (manual embedding/rename review)", "commercial": None, "adapt": None, "distribute": None, "attribution": None, "share_alike": None, "url": "https://openfontlicense.org/open-font-license-official-text/"},
    "OWNED": {"label": "Rights holder claim (unverified)", "commercial": None, "adapt": None, "distribute": None, "attribution": None, "share_alike": None, "url": ""},
    "CUSTOM": {"label": "Custom license / permission", "commercial": None, "adapt": None, "distribute": None, "attribution": None, "share_alike": None, "url": ""},
    "UNKNOWN": {"label": "Unknown / not determined", "commercial": None, "adapt": None, "distribute": None, "attribution": None, "share_alike": None, "url": ""},
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _db_path() -> Path:
    supplied = os.environ.get("ALDOL_RIGHTS_DB")
    if supplied:
        return Path(supplied).expanduser()
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base).expanduser() if base else Path.home() / ".local" / "share") / "aldol-rights" / "rights.sqlite3"


@contextmanager
def _db():
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    connection = sqlite3.connect(str(path), timeout=10)
    if os.name == "posix":
        os.chmod(path, 0o600)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("""CREATE TABLE IF NOT EXISTS assets (
        asset_id TEXT PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL,
        license_id TEXT NOT NULL, creator TEXT NOT NULL, rights_holder TEXT NOT NULL,
        source_url TEXT NOT NULL, license_url TEXT NOT NULL,
        evidence_url TEXT NOT NULL, notes TEXT NOT NULL, created_at TEXT NOT NULL
    )""")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _safe_url(url: str) -> bool:
    if not url:
        return True
    try:
        part = urlsplit(url)
        return part.scheme == "https" and bool(part.hostname) and not part.username and not part.password and len(url) <= 2048
    except ValueError:
        return False


def _nonempty(value: str, field: str, maxlen: int = 512) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    value = value.strip()
    if not value or len(value) > maxlen:
        raise ValueError(f"{field} must contain 1..{maxlen} characters")
    return value


def inspect_license(license_id: str) -> dict[str, Any]:
    """Return standard conditions, not a verification that a particular asset is licensed."""
    key = _nonempty(license_id, "license_id", 50).upper().replace("_", "-")
    details = LICENSES.get(key)
    if not details:
        return {"status": "UNKNOWN_LICENSE", "license_id": key, "supported_ids": sorted(LICENSES), "warning": "No rights determination; request source license review."}
    return {"status": "REFERENCE_ONLY", "license_id": key, **details,
            "warning": "A license label alone does not prove the asset has this license; verify the creator, source and original license."}


def register_asset(title: str, kind: str, license_id: str = "UNKNOWN", creator: str = "", rights_holder: str = "", source_url: str = "", license_url: str = "", evidence_url: str = "", notes: str = "") -> dict[str, Any]:
    title = _nonempty(title, "title", 300)
    kind = _nonempty(kind, "kind", 30).lower()
    if kind not in KINDS:
        raise ValueError("kind must be one of: " + ", ".join(sorted(KINDS)))
    license_id = _nonempty(license_id, "license_id", 50).upper().replace("_", "-")
    if license_id not in LICENSES:
        raise ValueError("unsupported license_id; use UNKNOWN or CUSTOM until reviewed")
    fields = [creator, rights_holder, source_url, license_url, evidence_url, notes]
    if any(not isinstance(x, str) for x in fields):
        raise ValueError("metadata fields must be text")
    if any(len(x) > 4096 for x in fields):
        raise ValueError("metadata field exceeds 4096 characters")
    if any(not _safe_url(u) for u in (source_url, license_url, evidence_url)):
        raise ValueError("URLs must be HTTPS and contain no embedded credentials")
    asset_id, created_at = uuid4().hex, _timestamp()
    with _db() as conn:
        conn.execute("INSERT INTO assets VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            asset_id, title, kind, license_id, creator.strip(), rights_holder.strip(),
            source_url.strip(), license_url.strip(), evidence_url.strip(), notes.strip(), created_at))
    return {"status": "REGISTERED_UNVERIFIED", "asset_id": asset_id, "title": title, "license_id": license_id,
            "created_at": created_at, "warning": "Registration records a claim, not ownership or permission verification."}


def _get_asset(asset_id: str) -> dict[str, Any] | None:
    with _db() as conn:
        record = conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
    return dict(record) if record else None


def _selected(asset_ids_json: str) -> list[dict[str, Any]]:
    try:
        ids = json.loads(asset_ids_json)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("asset_ids_json must be a JSON array of IDs") from exc
    if not isinstance(ids, list) or len(ids) > 500 or any(not isinstance(x, str) or len(x) > 100 for x in ids):
        raise ValueError("asset_ids_json must be a JSON array of at most 500 strings")
    if not ids:
        with _db() as conn:
            rows = conn.execute("SELECT * FROM assets ORDER BY created_at,asset_id LIMIT 501").fetchall()
        if len(rows) > 500:
            raise ValueError("More than 500 assets; supply asset_ids_json explicitly. An incomplete report is not allowed.")
        return [dict(x) for x in rows]
    assets = [_get_asset(x) for x in dict.fromkeys(ids)]
    missing = [x for x, a in zip(dict.fromkeys(ids), assets) if a is None]
    if missing:
        raise ValueError(f"unknown asset ids: {', '.join(missing[:10])}")
    return [a for a in assets if a is not None]


def _usage(asset: dict[str, Any], commercial: bool, modified: bool, redistribute: bool, attribution_planned: bool, derivative_license: str) -> dict[str, Any]:
    lic = LICENSES[asset["license_id"]]
    blocked: list[str] = []
    conditions: list[str] = []
    evidence: list[str] = []
    human_review: list[str] = []
    if not asset["source_url"]:
        evidence.append("Source URL missing")
    if not asset["evidence_url"]:
        evidence.append("Original license/permission evidence URL missing")
    if asset["license_id"].startswith("CC-") or asset["license_id"] == "CC0-1.0":
        if lic["commercial"] is False and commercial:
            blocked.append("NC: commercial use not permitted under the listed license")
        if lic["adapt"] is False and modified and redistribute:
            blocked.append("ND: sharing adapted material not permitted under the listed license")
        if lic["attribution"] and redistribute:
            if not asset["creator"]:
                evidence.append("Author/attribution name missing")
            if not attribution_planned:
                conditions.append("Display creator, title, source, license link and modification note where applicable")
        if lic["share_alike"] and modified and redistribute:
            if derivative_license.strip().upper() != asset["license_id"]:
                conditions.append("SA: confirm adapted output uses same or compatible license; v0.1 verifies exact match only")
            human_review.append("SA compatibility/scope requires human review")
        if asset["license_id"] == "CC0-1.0":
            human_review.append("Confirm public-domain dedication and any separate personality/trademark rights")
    else:
        human_review.append("No standardized scope; inspect underlying ownership/contract and permitted uses")
    if not asset["license_url"] and asset["license_id"] in ("CUSTOM",):
        evidence.append("Custom contract/license URL missing")
    human_review.append("Confirm the evidence actually applies to this asset and intended use")
    if blocked:
        status = "BLOCKED"
    elif evidence:
        status = "NEEDS_EVIDENCE"
    elif conditions:
        status = "CONDITIONAL"
    else:
        status = "READY_FOR_HUMAN_REVIEW"
    return {"asset_id": asset["asset_id"], "title": asset["title"], "license_id": asset["license_id"],
            "status": status, "blocked_reasons": blocked, "missing_evidence": evidence,
            "conditions": conditions, "human_review": human_review,
            "legal_clearance": False}


def check_usage(asset_id: str, commercial: bool = False, modified: bool = False,
                redistribute: bool = True, attribution_planned: bool = False, derivative_license: str = "") -> dict[str, Any]:
    asset = _get_asset(_nonempty(asset_id, "asset_id", 100))
    if not asset:
        return {"status": "NOT_FOUND", "asset_id": asset_id, "legal_clearance": False}
    return _usage(asset, commercial, modified, redistribute, attribution_planned, derivative_license)


def generate_credits(asset_ids_json: str = "[]", format: str = "markdown") -> dict[str, Any]:
    """Generate DRAFT credits; never mark missing author/source/license as attributed."""
    if format not in ("markdown", "text"):
        raise ValueError("format must be markdown or text")
    assets = _selected(asset_ids_json)
    lines: list[str] = []
    incomplete: list[str] = []
    for a in assets:
        license_id = a["license_id"]
        detail = LICENSES[license_id]
        needed = []
        if detail["attribution"] and not a["creator"]:
            needed.append("creator")
        if not a["source_url"]:
            needed.append("source_url")
        if not a["evidence_url"]:
            needed.append("evidence_url")
        if license_id in ("UNKNOWN", "CUSTOM", "OWNED", "MIT", "APACHE-2.0", "OFL-1.1"):
            needed.append("license or rights scope needs manual verification")
        if needed:
            incomplete.append(f"{a['asset_id']}: {', '.join(needed)}")
        desc = f"{a['title']} | {a['creator'] or 'creator unverified'} | {license_id} | source: {a['source_url'] or 'MISSING'} | license: {a['license_url'] or detail['url'] or 'MISSING'}"
        lines.append(("- " if format == "markdown" else "") + desc)
    return {"status": "DRAFT_REQUIRES_REVIEW", "format": format, "count": len(assets),
            "credits": "\n".join(lines), "incomplete": incomplete,
            "warning": "Check modification indication, attribution placement, separate notices and contracts before release."}


def rights_report(asset_ids_json: str = "[]", commercial: bool = True, modified: bool = False,
                  redistribute: bool = True, attribution_planned: bool = False, derivative_license: str = "") -> dict[str, Any]:
    assets = _selected(asset_ids_json)
    results = [_usage(a, commercial, modified, redistribute, attribution_planned, derivative_license) for a in assets]
    counts = {status: sum(x["status"] == status for x in results) for status in ("BLOCKED", "NEEDS_EVIDENCE", "CONDITIONAL", "READY_FOR_HUMAN_REVIEW")}
    return {"status": "REPORT_ONLY", "count": len(results), "counts": counts, "items": results,
            "legal_clearance": False, "warning": "Review each original license/contract. No automatic legal approval is issued."}
