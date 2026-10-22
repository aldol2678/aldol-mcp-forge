"""Shared, deterministic and offline-safe contract validation for ALDOL specialists."""
from __future__ import annotations
import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from contract_forge import parse_contract

MAX_FIELD = 4096
COMPANIES = ("seum", "bonsae", "majung")
ROOT = Path(__file__).resolve().parents[1]
_CONTRACTS = {}

def json_input(value: str, field: str, allowed: set[str]) -> dict:
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_FIELD:
        raise ValueError(field + " must be JSON text of 1..4096 characters")
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(field + " must be a JSON object, not an URL or free text") from exc
    if not isinstance(data, dict):
        raise ValueError(field + " must be a JSON object")
    extra = set(data) - allowed
    if extra:
        raise ValueError(field + " has unsupported keys: " + ", ".join(sorted(extra)))
    return data

def string(value, field: str, *, max_length: int = MAX_FIELD, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > max_length or (not allow_empty and not value.strip()):
        raise ValueError(field + " must be a nonempty bounded string")
    return value

def finite_number(value, field: str, *, zero: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(field + " must be a finite number")
    if value < 0 or (not zero and value == 0):
        raise ValueError(field + " must be " + ("positive" if not zero else "nonnegative"))
    return float(value)

def safe_path(value: str) -> str:
    value = string(value, "path", max_length=160)
    path = PurePosixPath(value)
    if (path.is_absolute() or "\\" in value or any(part in ("..", ".git", ".github")
        for part in path.parts) or path.as_posix() in (".", "")):
        raise ValueError("path is not a safe relative source path")
    return value

def source_url(value: str) -> str:
    value = string(value, "source_url", max_length=1000)
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.port not in (None, 443) or "." not in parsed.hostname):
        raise ValueError("source_url must be an HTTPS URL with a hostname")
    return value

def observation_date(value: str) -> str:
    value = string(value, "observed_at", max_length=10)
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("observed_at must be an ISO date YYYY-MM-DD") from exc
    if d > datetime.now(timezone.utc).date():
        raise ValueError("observed_at cannot be in the future")
    return value

def payload(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def contract(company: str) -> dict:
    if company not in COMPANIES:
        raise ValueError("Unknown company")
    if company not in _CONTRACTS:
        path = ROOT / "examples" / (company + "-mcp-contract.json")
        _CONTRACTS[company] = parse_contract(path.read_text(encoding="utf-8"))
    return _CONTRACTS[company]

def verify_output(company: str, name: str, output: dict) -> dict[str, str]:
    specs = [t for t in contract(company)["tools"] if t["name"] == name]
    if len(specs) != 1:
        raise ValueError("Tool not listed in canonical Forge contract")
    schema = specs[0]["output_schema"]
    required = schema["required"]
    if not isinstance(output, dict) or set(output) != set(schema["properties"]) or any(k not in output for k in required):
        raise ValueError("Implementation result differs from declared output contract")
    if any(not isinstance(v, str) for v in output.values()):
        raise ValueError("Implementation output must have string-valued contract fields")
    return output
