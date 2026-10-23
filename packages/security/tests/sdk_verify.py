"""Real MCP SDK 2.x in-memory and stdio checks, with no scanner/network calls."""
import asyncio
from contextlib import contextmanager
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp_server import app


@contextmanager
def workspace(path):
    keys = ("ALDOL_SECURITY_ROOT", "ALDOL_SECURITY_OSV_NETWORK")
    old = {key: os.environ.get(key) for key in keys}
    os.environ["ALDOL_SECURITY_ROOT"] = str(path)
    os.environ["ALDOL_SECURITY_OSV_NETWORK"] = "0"
    try:
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


async def check(client, root):
    expected = {
        "security_capabilities", "security_scan_trivy", "security_scan_osv",
        "security_inventory_sbom", "security_scan_all", "security_secret_guardian"
    }
    found = {tool.name for tool in (await client.list_tools()).tools}
    assert found == expected, f"unexpected MCP tools: {found}"
    first = await client.call_tool("security_capabilities", {})
    assert not first.is_error and first.structured_content, "capability call failed"
    blocked = await client.call_tool("security_scan_osv", {"subpath": "."})
    assert not blocked.is_error and blocked.structured_content, "OSV call failed"
    payload = blocked.structured_content
    if isinstance(payload, dict) and "result" in payload:
        payload = payload["result"]
    assert payload.get("status") == "BLOCKED", payload
    async def guardian(subpath="."):
        before = {p.name: (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns)
                  for p in root.iterdir() if p.is_file()}
        result = await client.call_tool("security_secret_guardian", {"subpath": subpath})
        assert not result.is_error and result.structured_content, "Guardian structured call failed"
        serialized = json.dumps(result.model_dump(mode="json"))
        assert all(value not in serialized for value in (
            "SYNTHETIC_SDK_VALUE", "OPENAI_API_KEY", "sdk-alias", str(root))), "redaction failed"
        after = {p.name: (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns)
                 for p in root.iterdir() if p.is_file()}
        assert before == after, "workspace mutation"
        data = result.structured_content
        return data.get("result", data)

    normal = await guardian()
    assert normal["credential_count"] == 1 and normal["status"] == "INVENTORIED"
    assert (await guardian("../"))["status"] == "BLOCKED"
    manifest = root / "secret-guardian.inventory.json"
    manifest.write_text('{"schema_version":1,"credentials":[{"ref":"sdk-alias","secret":"SYNTHETIC_SDK_VALUE"}]}')
    assert (await guardian())["status"] == "INCOMPLETE"
    manifest.unlink()
    return {"tool_count": len(found), "osv_offline_state": payload["status"],
            "guardian": {"normal": "INVENTORIED", "unsafe_path": "BLOCKED",
                         "invalid_manifest": "INCOMPLETE", "redacted": True, "readonly": True}}


async def main():
    from mcp import Client, StdioServerParameters
    from mcp.client.stdio import stdio_client
    with tempfile.TemporaryDirectory() as directory, workspace(directory):
        root = Path(directory)
        (root / ".env").write_text("OPENAI_API_KEY=SYNTHETIC_SDK_VALUE\n")
        (root / ".env").chmod(0o600)
        async with Client(app, raise_exceptions=True) as client:
            memory = await check(client, root)
        params = StdioServerParameters(
            command=sys.executable,
            args=["-B", str(Path(__file__).resolve().parents[1] / "mcp_server.py")],
            env={"ALDOL_SECURITY_ROOT": directory, "ALDOL_SECURITY_OSV_NETWORK": "0"},
        )
        async with Client(stdio_client(params), raise_exceptions=True) as client:
            stdio = await check(client, root)
    return {"sdk_version": importlib.metadata.version("mcp"), "inmemory": memory,
            "stdio": stdio, "passed": True, "network_used": False}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(asyncio.wait_for(main(), timeout=50))))
