"""ALDOL Security v0.1: strictly scoped, read-only scanner orchestration.

Only aggregate/allowlisted metadata leaves this module. Scanner stdout and
stderr, especially secret matches, MUST NEVER be returned to callers.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path, PurePath
import re
import shutil
import subprocess
import tempfile
from typing import Any

VERSION = "0.1.0"
MAX_OUTPUT = 12 * 1024 * 1024
MAX_ENTRIES = 30000
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN")
BINARIES = {"trivy": "trivy", "osv": "osv-scanner", "syft": "syft"}


def _timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def capabilities() -> dict[str, Any]:
    return {
        "name": "ALDOL SECURITY",
        "version": VERSION,
        "workspace_configured": bool(os.getenv("ALDOL_SECURITY_ROOT")),
        "scanners_installed": {k: bool(shutil.which(v)) for k, v in BINARIES.items()},
        "osv_external_lookup_enabled": os.getenv("ALDOL_SECURITY_OSV_NETWORK") == "1",
        "network_policy": "Trivy database auto-updates disabled; OSV requires opt-in",
        "source_mutation": False,
        "mobile": "Browser dashboard available when private HTTP service is hosted",
        "note": "Installed does not mean scan database is current or a scan passed.",
    }


def _scoped_path(subpath: str, *, validate_tree: bool = True) -> tuple[Path, Path]:
    raw = subpath.strip() if isinstance(subpath, str) else ""
    if not raw or len(raw) > 220 or "\x00" in raw:
        raise ValueError("invalid relative subpath")
    if Path(raw).is_absolute() or ".." in PurePath(raw).parts:
        raise ValueError("absolute or parent-traversal paths are forbidden")
    configured = os.environ.get("ALDOL_SECURITY_ROOT", "")
    if not configured:
        raise ValueError("ALDOL_SECURITY_ROOT is not configured")
    root = Path(configured).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("workspace root must be a directory")
    candidate = root
    for part in PurePath(raw).parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError("symbolic links are not permitted in scan targets")
    target = candidate.resolve(strict=True)
    if not target.is_relative_to(root):
        raise ValueError("target escapes configured workspace")
    if not target.is_dir():
        raise ValueError("target must be an existing directory")
    # Guardian performs its own bounded descriptor-relative traversal.
    if not validate_tree:
        return root, target
    # Reject symlinks rather than trusting scanner-dependent traversal behavior.
    def walk_error(_):
        raise ValueError("workspace traversal failed")
    seen = 0
    for current, dirs, names in os.walk(target, followlinks=False, onerror=walk_error):
        for name in dirs + names:
            seen += 1
            if seen > MAX_ENTRIES:
                raise ValueError("too many entries; narrow the subpath")
            if Path(current, name).is_symlink():
                raise ValueError("symbolic links are not permitted in scan targets")
    return root, target


def _safe_id(value: object) -> str:
    value = str(value) if value is not None else ""
    return re.sub(r"[^A-Za-z0-9._:-]", "", value)[:90]


def _blocked(tool: str, reason: str) -> dict[str, Any]:
    return {"scanner": tool, "status": "BLOCKED", "reason": reason, "scanned_at": _timestamp()}


def _unknown(tool: str, reason: str) -> dict[str, Any]:
    return {"scanner": tool, "status": "UNKNOWN", "reason": reason, "scanned_at": _timestamp()}


def _invoke(scanner: str, args: list[str], cwd: Path) -> dict[str, Any] | None:
    command = shutil.which(BINARIES[scanner])
    if command is None:
        return _unknown(scanner, "scanner binary is not installed")
    try:
        timeout = min(120, max(10, int(os.getenv("ALDOL_SECURITY_TIMEOUT", "75"))))
    except ValueError:
        timeout = 75
    # Deliberately do not propagate cloud tokens, GitHub credentials or proxies.
    env = {"PATH": os.getenv("PATH", "/usr/bin:/bin"), "HOME": "/tmp",
           "XDG_CACHE_HOME": "/tmp/aldol-security-cache"}
    if scanner == "trivy" and os.getenv("ALDOL_TRIVY_CACHE_DIR"):
        env["TRIVY_CACHE_DIR"] = os.environ["ALDOL_TRIVY_CACHE_DIR"]
    if scanner == "osv":
        # Network lookup is an explicit decision; no implicit proxy forwarding.
        if os.getenv("SSL_CERT_FILE"):
            env["SSL_CERT_FILE"] = os.environ["SSL_CERT_FILE"]
    try:
        with tempfile.TemporaryFile() as sink:
            proc = subprocess.run([command, *args], cwd=cwd, env=env,
                                  stdout=sink, stderr=subprocess.DEVNULL,
                                  timeout=timeout, check=False)
            length = sink.tell()
            if length > MAX_OUTPUT:
                return _unknown(scanner, "scanner output exceeded 12 MiB; narrow the scan")
            sink.seek(0)
            output = sink.read()
    except subprocess.TimeoutExpired:
        return _unknown(scanner, "scan timed out")
    except OSError:
        return _unknown(scanner, "scanner failed to start")
    # OSV returns 1 when vulnerabilities are present; other codes may also
    # represent findings depending on CLI version. Only parse valid JSON.
    if proc.returncode not in (0, 1):
        return _unknown(scanner, "scanner exited unsuccessfully")
    try:
        parsed = json.loads(output.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("not a JSON object")
    except (ValueError, UnicodeError):
        return _unknown(scanner, "scanner produced no valid JSON report")
    return parsed


def _trivy_report(data: dict[str, Any]) -> dict[str, Any]:
    counts = {k: 0 for k in SEVERITIES}
    secret_count = 0
    config_count = 0
    ids: list[str] = []
    for result in data.get("Results", []) or []:
        if not isinstance(result, dict):
            continue
        for finding in result.get("Vulnerabilities", []) or []:
            if not isinstance(finding, dict):
                continue
            severity = str(finding.get("Severity", "UNKNOWN")).upper()
            counts[severity if severity in counts else "UNKNOWN"] += 1
            identifier = _safe_id(finding.get("VulnerabilityID"))
            if identifier and identifier not in ids and len(ids) < 30:
                ids.append(identifier)
        secret_count += len(result.get("Secrets", []) or [])
        config_count += len(result.get("Misconfigurations", []) or [])
    total = sum(counts.values()) + secret_count + config_count
    return {"scanner": "trivy", "status": "FINDINGS" if total else "NO_FINDINGS_IN_SCOPE",
            "vulnerabilities": counts, "secret_matches": secret_count,
            "misconfigurations": config_count, "vulnerability_ids": ids,
            "scanned_at": _timestamp(),
            "privacy": "No secret value, matched line, file content, or raw scanner log exposed."}


def _osv_report(data: dict[str, Any]) -> dict[str, Any]:
    # OSV v2 machine output: results[].packages[].vulnerabilities[].
    ids: list[str] = []
    total = 0
    for result in data.get("results", []) or []:
        if not isinstance(result, dict):
            continue
        for pkg in result.get("packages", []) or []:
            if not isinstance(pkg, dict):
                continue
            for vuln in pkg.get("vulnerabilities", []) or []:
                total += 1
                if isinstance(vuln, dict):
                    identifier = _safe_id(vuln.get("id"))
                    if identifier and identifier not in ids and len(ids) < 30:
                        ids.append(identifier)
    return {"scanner": "osv", "status": "FINDINGS" if total else "NO_FINDINGS_IN_SCOPE",
            "vulnerability_matches": total, "vulnerability_ids": ids,
            "scanned_at": _timestamp()}


def _syft_report(data: dict[str, Any]) -> dict[str, Any]:
    items = data.get("components", [])
    if not isinstance(items, list):
        return _unknown("syft", "CycloneDX report has no component list")
    return {"scanner": "syft", "status": "INVENTORIED",
            "component_count": len(items), "format": "CycloneDX JSON",
            "scanned_at": _timestamp(),
            "privacy": "Raw SBOM is intentionally not returned by the MCP."}


def scan(tool: str, subpath: str = ".") -> dict[str, Any]:
    if tool not in BINARIES:
        raise ValueError("unknown scanner")
    if tool == "osv" and os.getenv("ALDOL_SECURITY_OSV_NETWORK") != "1":
        return _blocked("osv", "External vulnerability lookup is disabled; set ALDOL_SECURITY_OSV_NETWORK=1 to opt in")
    try:
        root, path = _scoped_path(subpath)
    except (OSError, ValueError) as exc:
        # Do not return path values or raw OS errors to MCP callers.
        return _blocked(tool, "workspace missing, unsafe, or outside allowed root")
    if tool == "trivy":
        args = ["fs", "--format", "json", "--quiet", "--scanners",
                "vuln,misconfig,secret", "--offline-scan", "--skip-db-update",
                "--skip-check-update", "--skip-java-db-update", str(path)]
        parser = _trivy_report
    elif tool == "osv":
        args = ["scan", "source", "--recursive", "--format", "json", str(path)]
        parser = _osv_report
    else:
        args = ["dir:" + str(path), "-o", "cyclonedx-json", "--quiet"]
        parser = _syft_report
    result = _invoke(tool, args, root)
    return result if result is not None and "status" in result else parser(result)


def scan_all(subpath: str = ".") -> dict[str, Any]:
    results = {tool: scan(tool, subpath) for tool in ("trivy", "osv", "syft")}
    statuses = [value["status"] for value in results.values()]
    if "FINDINGS" in statuses:
        overall = "FINDINGS_WITH_GAPS" if any(x in ("UNKNOWN", "BLOCKED") for x in statuses) else "FINDINGS"
    elif any(x in ("UNKNOWN", "BLOCKED") for x in statuses):
        overall = "INCOMPLETE"
    else:
        overall = "NO_FINDINGS_IN_COMPLETED_CHECKS"
    return {"name": "ALDOL SECURITY", "version": VERSION,
            "overall": overall, "scans": results, "scanned_at": _timestamp(),
            "disclaimer": "Not a penetration test, zero-risk claim, or proof of production security."}
