"""Real MCP Python SDK v2 integration test for Forge itself.

This intentionally tests trusted repository code only. Test output goes to an
ephemeral workspace and never contacts external APIs or deploys any project.
"""
import asyncio
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "forge_list_templates", "forge_preview", "forge_create",
    "forge_add_tool", "forge_test", "forge_package",
    "forge_preview_openapi", "forge_import_openapi",
}
SAMPLE_SPEC = (ROOT / "examples" / "pets_openapi.json").read_text(encoding="utf-8")

# Exact v0.3.2 legacy per-field semantics, ignoring SDK-generated titles/default.
ARGUMENTS = {
    "forge_list_templates": ({}, ()),
    "forge_preview": ({"description": (1, 2000)}, ("description",)),
    "forge_create": ({"project_name": (1, 40), "description": (1, 2000)},
                     ("project_name", "description")),
    "forge_add_tool": ({"project_name": (1, 40), "description": (1, 2000),
                        "isolation": (1, 40)}, ("project_name", "description")),
    "forge_test": ({"project_name": (1, 40), "isolation": (1, 40)},
                   ("project_name",)),
    "forge_package": ({"project_name": (1, 40), "isolation": (1, 40)},
                      ("project_name",)),
    "forge_preview_openapi": ({"spec_json": (2, 120000)}, ("spec_json",)),
    "forge_import_openapi": ({"project_name": (1, 40),
                             "spec_json": (2, 120000),
                             "isolation": (1, 40)}, ("project_name", "spec_json")),
}


def contract_check(tools):
    """Compare advertised schemas semantically, excluding cosmetics."""
    for tool in tools:
        fields, required = ARGUMENTS[tool.name]
        schema = tool.input_schema
        props = schema.get("properties", {})
        if schema.get("type") != "object" or set(props) != set(fields):
            raise AssertionError(f"{tool.name} properties differ: {schema}")
        if set(schema.get("required", [])) != set(required):
            raise AssertionError(f"{tool.name} required fields differ: {schema}")
        for name, (min_len, max_len) in fields.items():
            got = props[name]
            for key, value in (("type", "string"), ("minLength", min_len),
                               ("maxLength", max_len)):
                if got.get(key) != value:
                    raise AssertionError(f"{tool.name}.{name}.{key}: {got!r} != {value!r}")
            if name == "isolation" and set(got.get("enum", [])) != {"auto", "strict"}:
                raise AssertionError(f"{tool.name}.isolation enum: {got!r}")
    return {"schema_fields": sum(len(fields) for fields, _ in ARGUMENTS.values()),
            "all_required_and_bounds_matched": True}


async def expect_rejected(client, tool, args, hint=None):
    """Expected user mistakes must be observable tool errors, never successes."""
    reply = await client.call_tool(tool, args)
    if not reply.is_error or reply.structured_content is not None:
        raise AssertionError(f"{tool} accepted invalid arguments: {args!r} / {reply!r}")
    message = " ".join(getattr(block, "text", "") for block in reply.content)
    if not message.strip() or (hint and hint.lower() not in message.lower()):
        raise AssertionError(f"{tool} error message lost: {message!r}; expected {hint!r}")
    return message



def payload(response):
    if response.is_error:
        raise AssertionError(f"MCP tool returned error: {response}")
    data = response.structured_content
    if not isinstance(data, dict):
        raise AssertionError(f"Expected SDK v2 structured_content, received {data!r}")
    return data["result"] if isinstance(data.get("result"), dict) else data


async def check(client, mode):
    tools = (await client.list_tools()).tools
    names = {tool.name for tool in tools}
    if names != EXPECTED or len(tools) != len(EXPECTED):
        raise AssertionError(f"8 public tools changed: {sorted(names)}")
    schemas = contract_check(tools)

    # No mutation on invalid input; compare schema-validation and execution errors.
    await expect_rejected(client, "forge_preview", {})
    await expect_rejected(client, "forge_preview", {"description": ""})
    await expect_rejected(client, "forge_preview", {"description": "x" * 2001})
    await expect_rejected(client, "forge_preview", {"description": 3})
    await expect_rejected(client, "forge_preview",
                          {"description": "HTML 검사", "unrecognized": "not-allowed"})
    await expect_rejected(client, "forge_create",
                          {"project_name": "x" * 41, "description": "HTML 검사"})
    await expect_rejected(client, "forge_test",
                          {"project_name": "not-created", "isolation": "unsafe"})
    await expect_rejected(client, "forge_preview_openapi", {"spec_json": "{"})
    await expect_rejected(client, "forge_preview_openapi",
                          {"spec_json": "{" + "x" * 120010 + "}"})
    await expect_rejected(client, "forge_test",
                          {"project_name": "not-created"}, "Project does not exist")

    preview = payload(await client.call_tool("forge_preview", {"description": "HTML 게임 검사"}))
    assert preview.get("supported") is True and preview.get("template") == "html_audit", preview
    templates = payload(await client.call_tool("forge_list_templates", {}))
    assert "html_audit" in templates and "json_audit" in templates, templates
    api_preview = payload(await client.call_tool("forge_preview_openapi", {"spec_json": SAMPLE_SPEC}))
    assert api_preview.get("supported") is True and api_preview.get("count") == 2, api_preview
    assert api_preview.get("default_network_access") is False, api_preview

    # Both transports create, validate, and package into ephemeral workspaces.
    name = "ci-html-" + mode
    created = payload(await client.call_tool(
        "forge_create", {"project_name": name, "description": "HTML 게임 검사"}))
    assert created.get("created") is True and not created.get("auto_deployed"), created
    await expect_rejected(client, "forge_create",
                          {"project_name": name, "description": "HTML 게임 검사"}, "Project exists")
    verified = payload(await client.call_tool("forge_test", {"project_name": name}))
    assert verified.get("passed") is True, verified
    assert verified.get("compat_smoke_test") == "passed", verified
    assert verified.get("official_sdk") == "passed", verified
    packaged = payload(await client.call_tool("forge_package", {"project_name": name}))
    assert packaged.get("packaged") is True and packaged.get("deployed") is False, packaged
    assert Path(packaged["path"]).is_file(), packaged

    if mode == "stdio":
        api_name = "ci-pets-openapi"
        imported = payload(await client.call_tool(
            "forge_import_openapi", {"project_name": api_name, "spec_json": SAMPLE_SPEC}))
        assert imported.get("created") is True and imported.get("mode") == "dry_run_by_default", imported
        api_verified = payload(await client.call_tool("forge_test", {"project_name": api_name}))
        assert api_verified.get("passed") is True, api_verified
        assert api_verified.get("official_sdk") == "passed", api_verified
        for item in api_verified.get("sample_tool_results", {}).values():
            assert item["mode"] == "dry_run" and item["network_called"] is False, item

    return {"passed": True, "mode": mode, "tools": sorted(names),
            "contract": schemas, "errors_visible": True,
            "generated_mcp": name, "official_generated_sdk": "passed",
            "openapi_dry_run": mode == "stdio"}


async def verify():
    from mcp import Client, StdioServerParameters
    from mcp.client.stdio import stdio_client

    with tempfile.TemporaryDirectory(prefix="aldol-forge-sdk-") as folder:
        os.environ["ALDOL_FORGE_WORKSPACE_ROOT"] = folder
        os.environ["ALDOL_API_BASE_URL"] = ""
        os.environ["ALDOL_API_ALLOWED_HOST"] = ""

        # Must set env before importing Forge so its workspace override is used.
        sys.path.insert(0, str(ROOT))
        import forge_sdk

        async with Client(forge_sdk.app, raise_exceptions=True) as client:
            in_memory = await check(client, "inmemory")

        # Real child process, using a separate preexisting temp workspace.
        with tempfile.TemporaryDirectory(prefix="aldol-forge-stdio-") as stdio_folder:
            env = {
                "ALDOL_FORGE_WORKSPACE_ROOT": stdio_folder,
                "ALDOL_API_BASE_URL": "",
                "ALDOL_API_ALLOWED_HOST": "",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            params = StdioServerParameters(
                command=sys.executable, args=["-B", str(ROOT / "forge_sdk.py")],
                env=env,
            )
            async with Client(stdio_client(params), raise_exceptions=True) as client:
                stdio = await check(client, "stdio")
        return {"passed": True, "official_sdk_version": importlib.metadata.version("mcp"),
                "forge_entrypoint": "forge_sdk.py", "inmemory": in_memory,
                "stdio": stdio, "network_called": False, "production_deployed": False}


def main():
    try:
        import mcp  # noqa: F401
        if importlib.metadata.version("mcp").split(".")[0] != "2":
            raise RuntimeError("Official mcp==2.x required")
    except (ImportError, importlib.metadata.PackageNotFoundError) as exc:
        print(json.dumps({"passed": False, "status": "SDK_UNAVAILABLE", "error": str(exc)}))
        return 2

    try:
        result = asyncio.run(asyncio.wait_for(verify(), timeout=120))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        traceback.print_exception(exc, file=sys.stderr)
        print(json.dumps({"passed": False, "status": "FAILED",
                          "error": str(exc), "error_type": type(exc).__name__},
                         ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
