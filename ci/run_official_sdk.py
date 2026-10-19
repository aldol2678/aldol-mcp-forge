"""Run the existing official v2 SDK verifier for both generated MCP servers.

Never accepts external API variables or substitutes the offline compatibility layer.
A failure in either project fails this job; evidence is saved before exit.
"""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "ci-results"
PROJECTS = ("aldol-openapi-pets", "aldol-game-html-audit")

def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = {}
    success = True
    for name in PROJECTS:
        project = ROOT / "workspace" / "projects" / name
        env = dict(os.environ)
        env["ALDOL_API_BASE_URL"] = ""
        env["ALDOL_API_ALLOWED_HOST"] = ""
        try:
            run = subprocess.run(
                [sys.executable, str(ROOT / "verify_sdk.py"), str(project),
                 "--mode", "both"],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=90,
                check=False)
            try:
                payload = json.loads(run.stdout.strip())
            except json.JSONDecodeError:
                payload = {"passed": False, "status": "invalid_verifier_output",
                           "stdout_tail": run.stdout[-2000:]}
            passed = (
                run.returncode == 0
                and payload.get("passed") is True
                and payload.get("official_sdk") is True
                and payload.get("network_used") is False
                and set(payload.get("transports", {})) == {"inmemory", "stdio"}
            )
            if not passed:
                success = False
            entry = {"passed": passed, "exit_code": run.returncode,
                     "verification": payload,
                     "stderr_tail": run.stderr[-2000:] if run.stderr else ""}
        except subprocess.TimeoutExpired:
            success = False
            entry = {"passed": False, "status": "timeout"}
        results[name] = entry
        print(f"{name}: {'PASS' if entry['passed'] else 'FAIL'}", flush=True)
    report = {
        "project": "ALDOL MCP Forge",
        "target_version": "0.3.1",
        "sdk_pin": "mcp==2.0.0",
        "runner": "GitHub Actions / Python 3.12",
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "official_sdk_tested": all(
            e.get("verification", {}).get("official_sdk") is True
            for e in results.values()),
        "passed": success,
        "projects": results,
    }
    (OUTPUT / "sdk_v2_results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({"passed": success, "projects": {
        key: value["passed"] for key, value in results.items()
    }}, ensure_ascii=False))
    return 0 if success else 1

if __name__ == "__main__":
    raise SystemExit(main())
