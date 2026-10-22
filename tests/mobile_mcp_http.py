"""Real Streamable HTTP tools/list and tools/call against the local preview app.

This does not call the deployed Vercel preview. The deployed bearer key is not
available to this process.
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
KEY = "local-mcp-http-key-" + ("m" * 32)
BRIEF = json.dumps({
    "goal": "원정 현황",
    "components": [{
        "name": "Energy",
        "role": "현재 에너지",
        "states": ["default", "loading", "empty", "error"],
        "mobile_behavior": "390px 상단",
        "interaction": "호스트가 값을 공급",
    }],
}, ensure_ascii=False)


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _data(result):
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(result.content[0].text)


async def _exercise(port):
    headers = {
        "Authorization": "Bearer " + KEY,
        "Origin": "https://chatgpt.com",
    }
    results = []
    async with httpx2.AsyncClient(headers=headers, timeout=30) as http:
        async with streamable_http_client(f"http://127.0.0.1:{port}/bonsae/mcp", http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                names = sorted(tool.name for tool in listed.tools)
                assert names == ["analyze_design", "generate_design_spec", "review_visual"], names
                results.append({"test": "bonsae_tools_list", "status": "PASS", "tools": names})
                spec = _data(await session.call_tool("generate_design_spec", {"brief": BRIEF}))
                assert "specification" in spec and "constraints" in spec
                results.append({"test": "bonsae_tools_call", "status": "PASS", "tool": "generate_design_spec"})
        async with streamable_http_client(f"http://127.0.0.1:{port}/ui/mcp", http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                names = {tool.name for tool in listed.tools}
                assert names == {
                    "ui_catalog", "ui_validate", "ui_audit", "ui_review", "ui_review_markup",
                    "ui_generate", "ui_presets", "ui_import_bonsae",
                }, names
                results.append({"test": "ui_tools_list", "status": "PASS", "count": len(names)})
                handoff = _data(await session.call_tool("ui_import_bonsae", {
                    "bonsae_output_json": json.dumps(spec, ensure_ascii=False),
                    "preset": "forest",
                }))
                assert handoff["functional_ui_complete"] is False
                assert handoff["status"] == "HANDOFF_REVIEW_REQUIRED"
                results.append({"test": "ui_import_bonsae_tools_call", "status": "PASS"})
                generated = _data(await session.call_tool("ui_generate", {
                    "spec_json": handoff["ui_spec_json"],
                    "target": "web-html",
                    "quality_mode": "advisory",
                }))
                assert "Energy" in generated["preview_html"]
                results.append({"test": "ui_generate_tools_call", "status": "PASS"})
    return results


def main():
    port = _port()
    log_path = Path("/tmp/aldol-mobile-mcp-http.log")
    env = {**os.environ, "ALDOL_DESIGN_MCP_KEY": KEY, "NO_PROXY": "127.0.0.1,localhost"}
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
            cwd=ROOT, env=env, stdout=log, stderr=log,
        )
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(100):
                try:
                    if opener.open(f"http://127.0.0.1:{port}/health", timeout=1).status == 200:
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("local preview server did not become ready")
            try:
                opener.open(urllib.request.Request(
                    f"http://127.0.0.1:{port}/ui/mcp", data=b"{}", method="POST",
                ))
                raise AssertionError("anonymous MCP call should fail")
            except urllib.error.HTTPError as exc:
                assert exc.code == 401, exc.code
            results = asyncio.run(_exercise(port))
        finally:
            process.terminate()
            process.wait(timeout=10)
    log_text = log_path.read_text(errors="replace")
    if KEY in log_text:
        raise RuntimeError("MCP key was written to the server log")
    print(json.dumps({"results": results, "passed": len(results), "deployment": "local-only"}, indent=2))


if __name__ == "__main__":
    main()
