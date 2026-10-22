"""Secret Guardian v0.1: local-only, read-only secret metadata risk assessment."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any
from engine import _scoped_path, _timestamp

MANIFEST = "secret-guardian.inventory.json"
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", ".next", "dist", "build", "__pycache__"}
NAME_RE = re.compile(rb"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]{0,79})\s*=")
SENSITIVE_RE = re.compile(r"API_?KEY|SECRET|TOKEN|PASSWORD|PRIVATE_?KEY|ACCESS_?KEY|SERVICE_?ROLE|DATABASE_?URL|CONNECTION_?STRING|CREDENTIAL|_PAT$", re.I)
REF_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,63}$")
PROVIDERS = {"github", "vercel", "supabase", "gcp", "openai", "railway", "other"}
ENVIRONMENTS = {"production", "staging", "development", "test", "unknown"}
PRIVILEGES = {"admin", "owner", "root", "write", "read", "unknown"}
EXPOSURES = {"none", "suspected", "confirmed", "unknown"}
FIELDS = {"ref", "provider", "environment", "privilege", "owner", "last_rotated_at",
          "expires_at", "rotation_policy_days", "exposure_status"}
MAX_ITEMS, MAX_ENV_FILES, MAX_ISSUES = 300, 40, 300

def _now() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()

def _provider(name: str) -> str:
    upper = name.upper()
    for prefix, provider in (("GITHUB", "github"), ("GH_", "github"),
                             ("VERCEL", "vercel"), ("SUPABASE", "supabase"),
                             ("GCP", "gcp"), ("GOOGLE", "gcp"),
                             ("OPENAI", "openai"), ("RAILWAY", "railway")):
        if upper.startswith(prefix):
            return provider
    return "other"

def _issue(ref: str, code: str, severity: str) -> dict[str, str]:
    return {"credential_ref": ref, "code": code, "severity": severity}

def _date(value: object) -> dt.date | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("invalid date")
    return dt.date.fromisoformat(value)

def _metadata(root: Path, today: dt.date) -> tuple[list[dict], list[dict], bool, bool]:
    path = root / MANIFEST
    if not path.exists():
        return [], [], False, False
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            raise ValueError("unsafe metadata")
        data = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or set(data) != {"schema_version", "credentials"}
                or data["schema_version"] != 1 or not isinstance(data["credentials"], list)
                or len(data["credentials"]) > MAX_ITEMS):
            raise ValueError("invalid metadata")
        records, issues, used = [], [], set()
        for item in data["credentials"]:
            if not isinstance(item, dict) or set(item) - FIELDS:
                raise ValueError("invalid fields")
            ref = item.get("ref")
            if not isinstance(ref, str) or not REF_RE.fullmatch(ref) or ref in used:
                raise ValueError("invalid ref")
            used.add(ref)
            provider = item.get("provider", "other")
            environment = item.get("environment", "unknown")
            privilege = item.get("privilege", "unknown")
            exposure = item.get("exposure_status", "unknown")
            owner = item.get("owner")
            policy = item.get("rotation_policy_days")
            if (provider not in PROVIDERS or environment not in ENVIRONMENTS
                    or privilege not in PRIVILEGES or exposure not in EXPOSURES):
                raise ValueError("invalid category")
            if owner is not None and (not isinstance(owner, str) or not REF_RE.fullmatch(owner)):
                raise ValueError("invalid owner")
            if policy is not None and (type(policy) is not int or not 1 <= policy <= 3650):
                raise ValueError("invalid policy")
            rotated, expires = _date(item.get("last_rotated_at")), _date(item.get("expires_at"))
            if rotated is not None and rotated > today:
                raise ValueError("future rotation")
            records.append({"credential_ref": ref, "provider": provider,
                            "environment": environment, "source": "opt_in_metadata"})
            if exposure in {"suspected", "confirmed"}:
                issues.append(_issue(ref, "USER_REPORTED_EXPOSURE", "CRITICAL"))
            if expires is not None and expires <= today:
                issues.append(_issue(ref, "EXPIRED_BY_METADATA", "HIGH"))
            if policy is not None and rotated is not None and (today - rotated).days > policy:
                issues.append(_issue(ref, "ROTATION_OVERDUE_BY_METADATA", "MEDIUM"))
            if privilege in {"admin", "owner", "root"}:
                issues.append(_issue(ref, "BROAD_PRIVILEGE_REVIEW", "MEDIUM"))
            if rotated is None:
                issues.append(_issue(ref, "ROTATION_DATE_UNKNOWN", "LOW"))
            if not owner:
                issues.append(_issue(ref, "OWNER_UNKNOWN", "LOW"))
        return records, issues, True, False
    except (OSError, UnicodeError, ValueError, TypeError):
        return [], [], True, True

def _is_env(name: str) -> bool:
    return (name == ".env" or name.startswith(".env.")) and not name.endswith(
        (".example", ".sample", ".template"))

def _dotenv(root: Path) -> tuple[list[dict], list[dict], int, bool]:
    records, issues = [], []
    file_count, incomplete = 0, False
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        for name in files:
            if not _is_env(name):
                continue
            file_count += 1
            if file_count > MAX_ENV_FILES:
                incomplete = True
                break
            path = Path(current, name)
            try:
                mode = path.lstat()
                if not stat.S_ISREG(mode.st_mode) or mode.st_size > 131072:
                    incomplete = True
                    continue
                fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                with os.fdopen(fd, "rb") as stream:
                    for line in stream:
                        if b"=" not in line:
                            continue
                        left = line.split(b"=", 1)[0]
                        match = NAME_RE.match(left + b"=")
                        if not match:
                            continue
                        key_name = match.group(1).decode("ascii")
                        if not SENSITIVE_RE.search(key_name):
                            continue
                        if len(records) >= MAX_ITEMS:
                            incomplete = True
                            break
                        # Stable ref allows correlation without disclosing variable name/path.
                        relative = str(path.relative_to(root))
                        ref = "env-" + hashlib.sha256((relative + "\0" + key_name).encode()).hexdigest()[:16]
                        records.append({"credential_ref": ref, "provider": _provider(key_name),
                                        "environment": "unknown", "source": "dotenv_name_only"})
                        if mode.st_mode & stat.S_IROTH:
                            issues.append(_issue(ref, "DOTENV_WORLD_READABLE", "HIGH"))
            except (OSError, UnicodeError, ValueError):
                incomplete = True
        if file_count > MAX_ENV_FILES or len(records) >= MAX_ITEMS:
            break
    return records, issues, min(file_count, MAX_ENV_FILES), incomplete

def report(subpath: str = ".") -> dict[str, Any]:
    checked_at = _timestamp()
    try:
        _, root = _scoped_path(subpath)
    except (OSError, ValueError):
        return {"module": "Secret Guardian", "version": "0.1.0",
                "status": "BLOCKED", "reason": "workspace unavailable or unsafe",
                "checked_at": checked_at}
    metadata, meta_issues, present, invalid = _metadata(root, _now())
    dotenv, env_issues, env_count, truncated = _dotenv(root)
    records, all_issues = metadata + dotenv, meta_issues + env_issues
    issues = all_issues[:MAX_ISSUES]
    incomplete = invalid or truncated or len(all_issues) > MAX_ISSUES
    status = ("FINDINGS_WITH_GAPS" if incomplete else "FINDINGS") if issues else (
        "INCOMPLETE" if incomplete else "INVENTORIED" if records else "UNKNOWN")
    return {"module": "Secret Guardian", "version": "0.1.0",
            "status": status, "checked_at": checked_at,
            "credential_count": len(records), "records": records, "risks": issues,
            "risk_counts": {s: sum(i["severity"] == s for i in issues)
                            for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW")},
            "coverage": {"metadata_manifest_present": present,
                         "metadata_valid": not invalid if present else None,
                         "dotenv_files_scanned": env_count,
                         "complete_within_local_scope": not incomplete},
            "limitations": "Only user-supplied metadata and local dotenv variable names. No key values in output, account-wide inventory, verified breach detection, automatic rotation, cloud access, or network calls."}
