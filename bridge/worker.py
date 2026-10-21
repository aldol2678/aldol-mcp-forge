"""Trusted local job runner for Forge's five mutating/testing operations.

This program is NOT an HTTP service, authentication provider or sandbox.
A future authenticated gateway must supply --subject from VERIFIED platform
identity, and --workspace-root from operator configuration. Neither comes
from the MCP tool JSON or the model's arguments.

It runs the existing Forge implementation without changing generator code.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import forge  # noqa: E402

TOOL_FIELDS = {
    "forge_create": ({"project_name", "description"}, set()),
    "forge_add_tool": ({"project_name", "description"}, {"isolation"}),
    "forge_test": ({"project_name"}, {"isolation"}),
    "forge_package": ({"project_name"}, {"isolation"}),
    "forge_import_openapi": ({"project_name", "spec_json"}, {"isolation"}),
}
SUBJECT_RE = re.compile(r"^[a-zA-Z0-9_.:@-]{1,128}$")
SAFE_FIELDS = {
    "created", "updated", "project_name", "tools", "version", "skipped",
    "mode", "auto_deployed", "packaged", "deployed", "sha256",
    "passed", "checks", "sample_tool_results", "isolation",
    "network_isolated", "default_network_access", "official_sdk",
    "official_sdk_details", "sdk_available_locally", "compat_smoke_test",
    "note",
}


def validate_request(value: object) -> tuple[str, dict]:
    if not isinstance(value, dict) or set(value) != {"tool", "arguments"}:
        raise ValueError("Request must contain only tool and arguments")
    tool, args = value["tool"], value["arguments"]
    if tool not in TOOL_FIELDS or not isinstance(args, dict):
        raise ValueError("Unsupported tool or arguments")
    required, optional = TOOL_FIELDS[tool]
    if not required.issubset(args) or set(args) - required - optional:
        raise ValueError("Missing or unknown tool arguments")
    for key, item in args.items():
        if not isinstance(item, str):
            raise ValueError(f"{key} must be string")
        lo, hi = (2, 120000) if key == "spec_json" else ((1, 2000) if key == "description" else (1, 40))
        if not lo <= len(item) <= hi:
            raise ValueError(f"{key} length outside allowed range")
    if "isolation" in args and args["isolation"] not in ("auto", "strict"):
        raise ValueError("isolation must be auto or strict")
    forge._name(args["project_name"])
    return tool, args


def private_workspace(configured_root: str, verified_subject: str) -> Path:
    if not SUBJECT_RE.fullmatch(verified_subject):
        raise ValueError("Verified subject has invalid format")
    # Resolve a configured existing directory; never allow tool input to set it.
    configured = Path(configured_root).expanduser()
    if not configured.is_absolute() or configured.is_symlink():
        raise ValueError("The configured workspace root must be an absolute non-symlink")
    root = configured.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Configured workspace is not a directory")
    tenants = root / "tenants"
    if tenants.is_symlink():
        raise ValueError("Unsafe tenant directory")
    tenants.mkdir(mode=0o700, exist_ok=True)
    key = hashlib.sha256(verified_subject.encode("utf-8")).hexdigest()
    owned = tenants / key
    if owned.is_symlink():
        raise ValueError("Unsafe subject workspace")
    owned.mkdir(mode=0o700, exist_ok=True)
    if not owned.resolve(strict=True).is_relative_to(root):
        raise ValueError("Workspace escaped configured root")
    if stat.S_IMODE(owned.stat().st_mode) & 0o077:
        raise ValueError("Tenant workspace cannot be group or world accessible")
    return owned


@contextmanager
def serialized_workspace(space: Path):
    path = space / ".forge-bridge.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def run(configured_root: str, subject: str, request: object) -> dict:
    tool, args = validate_request(request)
    space = private_workspace(configured_root, subject)
    # The core still uses module-level directories; only one operation runs
    # per process. Different subjects must be launched in separate processes.
    forge.SPACE = space
    forge.PROJECTS = space / "projects"
    forge.PACKAGES = space / "packages"
    forge.HISTORY = space / "history"

    # No live OpenAPI target can be configured by this bridge. This does not
    # replace network namespace isolation for executing untrusted code.
    os.environ.pop("ALDOL_API_BASE_URL", None)
    os.environ.pop("ALDOL_API_ALLOWED_HOST", None)

    actions = {
        "forge_create": forge._create,
        "forge_add_tool": forge._add_tool,
        "forge_test": forge._test,
        "forge_package": forge._package,
        "forge_import_openapi": forge._import_openapi,
    }
    with serialized_workspace(space):
        if tool in ("forge_create", "forge_import_openapi"):
            # Conservative per-user project count until a quota service exists.
            projects = forge.PROJECTS
            if projects.exists() and sum(
                p.is_dir() and not p.name.startswith(".") for p in projects.iterdir()
            ) >= 20:
                raise ValueError("Workspace project limit reached")
        output = actions[tool](args)
        if not isinstance(output, dict):
            raise RuntimeError("Unexpected Forge result")
        result = {key: value for key, value in output.items() if key in SAFE_FIELDS}
        if tool == "forge_package":
            # Persist by approved artifact ID, never expose backend paths.
            result["artifact_id"] = output["sha256"]
            result["bytes"] = Path(output["path"]).stat().st_size
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Trusted Forge Python bridge worker")
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--subject", required=True, help="Must be verified by the caller")
    ns = parser.parse_args()
    try:
        # JSON-only stdin. Reject unknown identity or workspace fields.
        raw = sys.stdin.buffer.read(160_001)
        if len(raw) > 160_000:
            raise ValueError("Request body exceeds 160000 bytes")
        request = json.loads(raw)
        result = run(ns.workspace_root, ns.subject, request)
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False))
        return 0
    except (ValueError, RuntimeError, OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        message = str(exc).replace(ns.workspace_root, "[workspace]")
        print(json.dumps({"ok": False, "error": message[:300]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
