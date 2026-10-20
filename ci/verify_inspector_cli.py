"""Verify ALDOL Forge using the official MCP Inspector CLI v2 client.

This is a separate, real MCP client process. Unlike the Python SDK harness,
each Inspector command starts a fresh stdio connection to Forge.

No deployment or live API calls; only trusted repository source is launched.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "ci-results" / "inspector-client-verification.json"
INSPECTOR = "@modelcontextprotocol/inspector@2.11.0"
EXPECTED = {
    "forge_list_templates", "forge_preview", "forge_create",
    "forge_add_tool", "forge_test", "forge_package",
    "forge_preview_openapi", "forge_import_openapi",
}


def request(method: str, *, tool: str | None = None, args: dict | None = None):
    command = [
        "npx", "--yes", INSPECTOR, "--cli",
        sys.executable, str(ROOT / "forge_sdk.py"),
        "--method", method, "--format", "json",
    ]
    if tool:
        command += ["--tool-name", tool]
        if args is not None:
            command += ["--tool-args-json", json.dumps(args, ensure_ascii=False)]
    process = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True,
        timeout=100, check=False,
    )
    stdout = process.stdout.strip()
    if process.returncode != 0:
        raise AssertionError(
            f"Inspector {method}/{tool} exited {process.returncode}; "
            f"stdout={stdout[-1600:]!r}; stderr={process.stderr[-1600:]!r}"
        )
    try:
        output = json.loads(stdout)
    except ValueError as error:
        raise AssertionError(
            f"Inspector output not JSON: {stdout[-1600:]!r}; "
            f"stderr={process.stderr[-800:]!r}"
        ) from error
    if not isinstance(output, dict):
        raise AssertionError(f"Inspector returned unexpected type: {type(output)}")
    if output.get("error"):
        raise AssertionError(f"Inspector returned an error: {output['error']}")
    return output.get("result", output)


def tool_result(result):
    if not isinstance(result, dict):
        raise AssertionError(f"Invalid tools/call result: {result!r}")
    if result.get("isError") or result.get("is_error"):
        raise AssertionError(f"MCP tool returned isError: {result!r}")
    data = result.get("structuredContent") or result.get("structured_content")
    if data is None:
        for item in result.get("content", []):
            if item.get("type") == "text":
                try:
                    data = json.loads(item["text"])
                    break
                except (KeyError, ValueError):
                    continue
    if not isinstance(data, dict):
        raise AssertionError(f"No structured or textual JSON result: {result!r}")
    return data.get("result") if isinstance(data.get("result"), dict) else data


def verify():
    identity = request("initialize")
    if not isinstance(identity, dict) or not identity.get("serverInfo"):
        raise AssertionError(f"Inspector initialize missing serverInfo: {identity!r}")
    tools_result = request("tools/list")
    if not isinstance(tools_result, dict):
        raise AssertionError(f"Inspector tools/list output unexpected: {tools_result!r}")
    tools = tools_result.get("tools", [])
    names = [item.get("name") for item in tools]
    if set(names) != EXPECTED or len(names) != 8:
        raise AssertionError(f"Inspector tool discovery differs: {names!r}")

    preview = tool_result(request(
        "tools/call", tool="forge_preview",
        args={"description": "HTML 게임 검사"},
    ))
    if preview.get("supported") is not True or preview.get("template") != "html_audit":
        raise AssertionError(f"Unexpected preview payload: {preview!r}")

    created = tool_result(request(
        "tools/call", tool="forge_create",
        args={"project_name": "inspector-html-audit", "description": "HTML 게임 검사"},
    ))
    if created.get("created") is not True or created.get("auto_deployed") is not False:
        raise AssertionError(f"Unexpected create payload: {created!r}")
    verified = tool_result(request(
        "tools/call", tool="forge_test",
        args={"project_name": "inspector-html-audit"},
    ))
    if (verified.get("passed") is not True
            or verified.get("official_sdk") != "passed"):
        raise AssertionError(f"Generated MCP verification did not pass: {verified!r}")
    packaged = tool_result(request(
        "tools/call", tool="forge_package",
        args={"project_name": "inspector-html-audit"},
    ))
    if packaged.get("packaged") is not True or packaged.get("deployed") is not False:
        raise AssertionError(f"Unexpected package result: {packaged!r}")
    if not Path(packaged["path"]).is_file():
        raise AssertionError("Forge did not produce the local ZIP")

    return {
        "passed": True,
        "client": "MCP Inspector CLI",
        "inspector_version_pin": "2.11.0",
        "server": "forge_sdk.py",
        "transport": "stdio",
        "initialized": True,
        "tools_found": sorted(names),
        "preview_passed": True,
        "create_passed": True,
        "generated_sdk_test_passed": True,
        "package_passed": True,
        "external_api_called": False,
        "deployed": False,
        "client_scope": "Inspector CLI, not ChatGPT/Claude desktop",
    }


def main():
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ
    env["ALDOL_API_BASE_URL"] = ""
    env["ALDOL_API_ALLOWED_HOST"] = ""
    try:
        with tempfile.TemporaryDirectory(prefix="aldol-inspector-") as folder:
            env["ALDOL_FORGE_WORKSPACE_ROOT"] = folder
            report = verify()
        exit_code = 0
    except Exception as error:
        traceback.print_exception(error, file=sys.stderr)
        report = {
            "passed": False,
            "status": "FAILED",
            "error": str(error)[-2000:],
            "client": "MCP Inspector CLI",
            "inspector_version_pin": "2.11.0",
        }
        exit_code = 1
    RESULT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
