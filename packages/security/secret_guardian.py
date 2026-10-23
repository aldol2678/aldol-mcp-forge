"""Secret Guardian v0.1: local-only, read-only secret metadata risk assessment."""
from __future__ import annotations
import datetime as dt
import hashlib
import hmac
import secrets
import json
import os
import re
import stat
from typing import Any
from engine import _scoped_path, _timestamp, MAX_ENTRIES
from guardian_io import directory, read_file, workspace

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

def _metadata(root_fd: int, today: dt.date, reference) -> tuple[list[dict], list[dict], bool, bool]:
    try:
        os.stat(MANIFEST, dir_fd=root_fd, follow_symlinks=False)
    except FileNotFoundError:
        return [], [], False, False
    except OSError:
        return [], [], True, True
    try:
        raw, _ = read_file(root_fd, MANIFEST, 65536)
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_invalid_constant)
        if (not isinstance(data, dict) or set(data) != {"schema_version", "credentials"}
                or type(data["schema_version"]) is not int or data["schema_version"] != 1 or not isinstance(data["credentials"], list)
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
            # Hash operator aliases too: an accidentally pasted credential must not leak.
            ref = reference("meta", ref)
            provider = item.get("provider", "other")
            environment = item.get("environment", "unknown")
            privilege = item.get("privilege", "unknown")
            exposure = item.get("exposure_status", "unknown")
            owner = item.get("owner")
            policy = item.get("rotation_policy_days")
            if (any(not isinstance(value, str) for value in (provider, environment, privilege, exposure))
                    or provider not in PROVIDERS or environment not in ENVIRONMENTS
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
                            "environment": environment, "source": "opt_in_metadata",
                            "unknown_metadata": [field for field, unknown in (
                                ("provider", "provider" not in item),
                                ("environment", environment == "unknown"),
                                ("privilege", privilege == "unknown"),
                                ("exposure_status", exposure == "unknown"),
                                ("owner", owner is None),
                                ("last_rotated_at", rotated is None),
                                ("expires_at", expires is None),
                                ("rotation_policy_days", policy is None)) if unknown]})
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
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
        return [], [], True, True

def _is_env(name: str) -> bool:
    return (name == ".env" or name.startswith(".env.")) and not name.endswith(
        (".example", ".sample", ".template"))

class _UnsafeTree(ValueError):
    pass


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _invalid_constant(_):
    raise ValueError("invalid JSON constant")


def _dotenv(root_fd: int, reference, remaining_items: int) -> tuple[list[dict], list[dict], int, bool]:
    records, issues = [], []
    file_count, attempted, seen, incomplete = 0, 0, 0, False

    def walk(fd, relative="", depth=0, excluded=False):
        nonlocal file_count, attempted, seen, incomplete
        if depth > 64:
            incomplete = True
            return
        try:
            before = os.fstat(fd)
            with os.scandir(fd) as entries:
                for entry in entries:
                    seen += 1
                    if seen > MAX_ENTRIES:
                        incomplete = True
                        return
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode):
                        raise _UnsafeTree("symbolic links are not permitted")
                    name = entry.name
                    relative_name = relative + name
                    if stat.S_ISDIR(info.st_mode):
                        if not excluded and _is_env(name):
                            incomplete = True
                        with directory(name, fd) as child:
                            walk(child, relative_name + "/", depth + 1,
                                 excluded or name in SKIP_DIRS)
                        if seen > MAX_ENTRIES:
                            return
                    elif not excluded and _is_env(name):
                        if attempted >= MAX_ENV_FILES:
                            incomplete = True
                            continue
                        attempted += 1
                        try:
                            raw, mode = read_file(fd, name, 131072)
                            file_count += 1
                            for line in raw.splitlines():
                                # Values only pass through the bounded read buffer;
                                # never retain, hash, evaluate or return them.
                                left = line.split(b"=", 1)[0]
                                match = NAME_RE.match(left + b"=") if b"=" in line else None
                                if not match:
                                    continue
                                key_name = match.group(1).decode("ascii")
                                if not SENSITIVE_RE.search(key_name):
                                    continue
                                if len(records) >= remaining_items:
                                    incomplete = True
                                    break
                                ref = reference("env", relative_name + "\0" + key_name)
                                if any(record["credential_ref"] == ref for record in records):
                                    continue
                                records.append({"credential_ref": ref, "provider": _provider(key_name),
                                                "environment": "unknown", "source": "dotenv_name_only",
                                                "unknown_metadata": ["environment", "privilege", "owner",
                                                    "last_rotated_at", "expires_at", "rotation_policy_days",
                                                    "exposure_status"]})
                                if mode.st_mode & stat.S_IROTH:
                                    issues.append(_issue(ref, "DOTENV_WORLD_READABLE", "HIGH"))
                        except (OSError, UnicodeError, ValueError):
                            incomplete = True
            after = os.fstat(fd)
            if (before.st_mtime_ns, before.st_ctime_ns) != (after.st_mtime_ns, after.st_ctime_ns):
                incomplete = True
        except OSError:
            incomplete = True

    walk(root_fd)
    return records, issues, file_count, incomplete

def report(subpath: str = ".") -> dict[str, Any]:
    checked_at = _timestamp()
    try:
        _, root = _scoped_path(subpath, validate_tree=False)
    except (OSError, ValueError):
        return {"module": "Secret Guardian", "version": "0.1.0",
                "status": "BLOCKED", "reason": "workspace unavailable or unsafe",
                "checked_at": checked_at}
    # Per-report key is discarded and never emitted. Same names cannot be
    # correlated across requests, processes or workspaces by guessing hashes.
    key = secrets.token_bytes(32)
    def reference(kind, value):
        digest = hmac.new(key, (kind + "\0" + value).encode("utf-8"), hashlib.sha256)
        return kind + "-" + digest.hexdigest()[:16]

    try:
        with workspace(root) as root_fd:
            before = os.fstat(root_fd)
            metadata, meta_issues, present, invalid = _metadata(root_fd, _now(), reference)
            dotenv, env_issues, env_count, truncated = _dotenv(root_fd, reference, MAX_ITEMS - len(metadata))
            after = os.fstat(root_fd)
            truncated |= (before.st_mtime_ns, before.st_ctime_ns) != (after.st_mtime_ns, after.st_ctime_ns)
    except _UnsafeTree:
        return {"module": "Secret Guardian", "version": "0.1.0", "status": "BLOCKED",
                "reason": "workspace unavailable or unsafe", "checked_at": checked_at}
    except (OSError, ValueError, NotImplementedError):
        return {"module": "Secret Guardian", "version": "0.1.0", "status": "INCOMPLETE",
                "reason": "workspace read interrupted or unsupported", "checked_at": checked_at}
    records, all_issues = metadata + dotenv, meta_issues + env_issues
    priority = {severity: rank for rank, severity in enumerate(("CRITICAL", "HIGH", "MEDIUM", "LOW"))}
    all_issues.sort(key=lambda issue: priority[issue["severity"]])
    issues = all_issues[:MAX_ISSUES]
    incomplete = invalid or truncated or len(all_issues) > MAX_ISSUES
    status = ("FINDINGS_WITH_GAPS" if incomplete else "FINDINGS") if issues else (
        "INCOMPLETE" if incomplete else "INVENTORIED" if records else "UNKNOWN")
    return {"module": "Secret Guardian", "version": "0.1.0",
            "status": status, "checked_at": checked_at,
            "reference_scope": "report", "reference_scheme": "hmac-sha256-64-v1",
            "credential_count": len(records), "records": records, "risks": issues,
            "risk_counts": {s: sum(i["severity"] == s for i in issues)
                            for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW")},
            "coverage": {"metadata_manifest_present": present,
                         "metadata_valid": not invalid if present else None,
                         "dotenv_files_scanned": env_count,
                         "complete_within_local_scope": not incomplete,
                         "metadata_assurance": "user_reported_unverified" if present and not invalid else "unknown",
                         "unknown_metadata_records": sum(bool(r["unknown_metadata"]) for r in records)},
            "limitations": "Only user-supplied metadata and local dotenv variable names. No key values in output, account-wide inventory, verified breach detection, automatic rotation, cloud access, or network calls."}
