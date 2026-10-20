"""Verify a downloaded ChatGPT Sites Forge Studio ZIP using the REAL MCP SDK v2.

Never execute arbitrary ZIP code: reject extra/unsafe members, verify SHA256SUMS,
then compare every executable file against the original Python Forge generator.
Only after exact source validation may verify_sdk.py import and run the server.
Intended for trusted CI/private execution, not a public ZIP upload endpoint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import forge  # noqa: E402

CURATED = frozenset({
    "server.py", "templates.py", "mcp_runtime.py", "requirements.txt",
    "README.md", "manifest.json",
})
OPENAPI = frozenset({
    "server.py", "operations.py", "api_runtime.py", "mcp_runtime.py",
    "requirements.txt", "openapi.json", "README.md", "manifest.json",
})
EXPORT = frozenset({"mcp-config.json", "studio-validation.json", "SHA256SUMS"})
ALLOWED = CURATED | OPENAPI | EXPORT
MAX_ZIP_BYTES = 1_000_000
MAX_UNCOMPRESSED_BYTES = 1_000_000
MAX_FILE_BYTES = 240_000


def validated_archive(archive: Path, target: Path) -> dict:
    if not archive.is_file() or archive.stat().st_size > MAX_ZIP_BYTES:
        raise ValueError("ZIP missing or exceeds maximum size")
    with ZipFile(archive) as z:
        members = z.infolist()
        names = [i.filename for i in members]
        if len(names) != len(set(names)) or not names or len(names) > len(ALLOWED):
            raise ValueError("Duplicate or excessive ZIP members")
        if any(n not in ALLOWED for n in names):
            raise ValueError("Unexpected ZIP member or unsafe path")
        if any(i.is_dir() or i.flag_bits & 0x1
               or (i.external_attr >> 16) & 0o170000 == 0o120000
               or i.file_size > MAX_FILE_BYTES for i in members):
            raise ValueError("Directory, symlink, encrypted or oversized ZIP member")
        if sum(i.file_size for i in members) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("Uncompressed ZIP exceeds limit")
        if z.testzip() is not None:
            raise ValueError("ZIP CRC check failed")
        files = {n: z.read(n) for n in names}

    if "manifest.json" not in files or "SHA256SUMS" not in files:
        raise ValueError("Manifest and SHA256SUMS are required")
    manifest = json.loads(files["manifest.json"].decode("utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Invalid manifest")
    kind = manifest.get("kind", "curated")
    source_set = OPENAPI if kind == "openapi-get" else CURATED if kind == "curated" else None
    if source_set is None or set(files) != (source_set | EXPORT):
        raise ValueError("Unexpected exported project file list")
    project_name = forge._name(manifest.get("name"))
    hashes = {}
    for line in files["SHA256SUMS"].decode("utf-8").splitlines():
        matched = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        if matched is None or matched[2] in hashes:
            raise ValueError("Malformed SHA256SUMS")
        hashes[matched[2]] = matched[1]
    if set(hashes) != set(files) - {"SHA256SUMS"}:
        raise ValueError("SHA256SUMS entries do not match archive")
    for name, expected in hashes.items():
        if hashlib.sha256(files[name]).hexdigest() != expected:
            raise ValueError("Archive SHA-256 mismatch: " + name)
    for name in source_set:
        dest = target / name
        dest.write_bytes(files[name])
    # Exact trusted generator comparison is mandatory before importing Python.
    previous = forge.PROJECTS
    try:
        forge.PROJECTS = target.parent
        if kind == "curated":
            forge._validated(project_name)
        else:
            forge._validated_openapi(project_name)
    finally:
        forge.PROJECTS = previous
    return {"project_name": project_name, "kind": kind,
            "version": manifest.get("version"), "files_checked": len(hashes)}


def verify(path: str) -> dict:
    archive = Path(path).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="forge-studio-sdk-") as folder:
        project_root = Path(folder) / "projects"
        project_root.mkdir(mode=0o700)
        # Determine a candidate directory name without executing ZIP source.
        with ZipFile(archive) as z:
            manifest = json.loads(z.read("manifest.json").decode("utf-8"))
        name = forge._name(manifest.get("name"))
        target = project_root / name
        target.mkdir(mode=0o700)
        metadata = validated_archive(archive, target)
        env = dict(os.environ)
        env["ALDOL_API_BASE_URL"] = ""
        env["ALDOL_API_ALLOWED_HOST"] = ""
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "verify_sdk.py"),
             str(target), "--mode", "both"],
            capture_output=True, text=True, timeout=90, check=False, env=env,
            cwd=ROOT,
        )
        try:
            report = json.loads(result.stdout.strip())
        except json.JSONDecodeError as exc:
            raise RuntimeError("Official SDK verifier did not return JSON") from exc
        passed = (
            result.returncode == 0 and report.get("passed") is True
            and report.get("official_sdk") is True
            and report.get("network_used") is False
            and set(report.get("transports", {})) == {"inmemory", "stdio"}
        )
        if not passed:
            return {**metadata, "passed": False,
                    "status": report.get("status", "SDK_FAILED"),
                    "sdk_version": report.get("sdk_version"),
                    "official_sdk": "FAIL"}
        return {**metadata, "passed": True, "official_sdk": "PASS",
                "sdk_version": report["sdk_version"],
                "inmemory": "PASS", "stdio": "PASS",
                "network_used": False,
                "security_boundary": "trusted generator parity before execution"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", help="A downloaded Forge Studio ZIP")
    args = parser.parse_args()
    try:
        result = verify(args.archive)
    except (OSError, ValueError, RuntimeError, BadZipFile, KeyError,
            json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        result = {"passed": False, "status": "REJECTED",
                  "reason": type(error).__name__}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
