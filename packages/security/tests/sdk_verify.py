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


async def check(client):
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
    return {"tool_count": len(found), "osv_offline_state": payload["status"]}


async def main():
    from mcp import Client, StdioServerParameters
    from mcp.client.stdio import stdio_client
    with tempfile.TemporaryDirectory() as directory, workspace(directory):
        async with Client(app, raise_exceptions=True) as client:
            memory = await check(client)
        params = StdioServerParameters(
            command=sys.executable,
            args=["-B", str(Path(__file__).resolve().parents[1] / "mcp_server.py")],
            env={"ALDOL_SECURITY_ROOT": directory, "ALDOL_SECURITY_OSV_NETWORK": "0"},
        )
        async with Client(stdio_client(params), raise_exceptions=True) as client:
            stdio = await check(client)
    return {"sdk_version": importlib.metadata.version("mcp"), "inmemory": memory,
            "stdio": stdio, "passed": True, "network_used": False}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(asyncio.wait_for(main(), timeout=50))))
