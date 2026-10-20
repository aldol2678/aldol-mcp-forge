import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import httpx2
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_service import upload, HTML, zipped

SERVER = Path(__file__).resolve().parents[1] / "server.py"
TOOLS = {
    "inspect_game_artifact",
    "run_static_qa",
    "run_browser_qa",
    "run_game_scenarios",
    "compare_game_versions",
    "get_qa_report",
}


def payload(r):
    assert not r.is_error, r
    return json.loads(r.content[0].text)


async def exercise(session):
    await session.initialize()
    listing = await session.list_tools()
    assert {t.name for t in listing.tools} == TOOLS
    a = payload(await session.call_tool("run_static_qa", {"artifact": upload()}))
    assert a["status"] == "PASS"
    z = payload(
        await session.call_tool(
            "inspect_game_artifact", {"artifact": zipped([("index.html", HTML)])}
        )
    )
    assert z["status"] == "PASS" and z["artifact"]["files_count"] == 1
    assert payload(await session.call_tool("get_qa_report", {"qa_id": a["qa_id"]})) == a
    b = payload(
        await session.call_tool(
            "run_static_qa", {"artifact": upload("<title>bad</title>")}
        )
    )
    assert b["status"] == "FAIL"
    r = payload(
        await session.call_tool(
            "compare_game_versions",
            {"baseline_id": a["qa_id"], "candidate_id": b["qa_id"]},
        )
    )
    assert r["status"] == "FAIL"
    assert (
        payload(await session.call_tool("run_browser_qa", {"artifact": upload()}))[
            "status"
        ]
        == "UNKNOWN"
    )
    assert (
        await session.call_tool(
            "run_static_qa", {"artifact": upload(), "unknown": True}
        )
    ).is_error
    assert (
        await session.call_tool(
            "inspect_game_artifact",
            {"artifact": {"filename": "x.html", "path": "/etc/passwd"}},
        )
    ).is_error
    assert (await session.call_tool("get_qa_report", {"qa_id": "../secret"})).is_error
    return {
        "tools": sorted(TOOLS),
        "static_status": a["status"],
        "qa_id": a["qa_id"],
        "regression": r["status"],
        "normal_shutdown": True,
    }


def test_stdio(tmp_path):
    assert SERVER.is_file()

    async def run():
        env = {**os.environ, "GAME_OPS_REPORT_ROOT": str(tmp_path / "reports")}
        async with stdio_client(
            StdioServerParameters(command=sys.executable, args=[str(SERVER)], env=env)
        ) as (read, write):
            async with ClientSession(read, write) as session:
                return await exercise(session)

    evidence = asyncio.run(run())
    target = os.environ.get("GAME_OPS_EVIDENCE")
    if target:
        Path(target).write_text(json.dumps(evidence, indent=2))


@pytest.fixture
def http_server(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    token = "local-test-only-credential-0000000000000000"
    proc = subprocess.Popen(
        [sys.executable, str(SERVER), "--http"],
        env={
            **os.environ,
            "PORT": str(port),
            "GAME_OPS_TOKEN": token,
            "GAME_OPS_REPORT_ROOT": str(tmp_path / "reports"),
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if proc.poll() is not None:
                raise AssertionError("HTTP server exited")
            try:
                if (
                    httpx2.get(
                        base + "/healthz", trust_env=False, timeout=1
                    ).status_code
                    == 200
                ):
                    break
            except Exception:
                time.sleep(0.05)
        else:
            raise AssertionError("server not ready")
        yield base, token
    finally:
        proc.terminate()
        proc.wait(timeout=8)


def test_http_auth_and_sdk(http_server):
    base, token = http_server
    for h in ({}, {"Authorization": "Bearer incorrect"}):
        assert httpx2.post(base + "/mcp", headers=h, trust_env=False).status_code == 401
    h = {"Authorization": "Bearer " + token}
    assert (
        httpx2.post(
            base + "/mcp",
            headers={**h, "Origin": "https://evil.invalid"},
            trust_env=False,
        ).status_code
        == 403
    )
    assert (
        httpx2.post(
            base + "/mcp",
            headers=h,
            content="x" * (3 * 1024 * 1024 + 1),
            trust_env=False,
        ).status_code
        == 413
    )

    async def run():
        async with httpx2.AsyncClient(headers=h, trust_env=False) as client:
            async with streamable_http_client(
                base + "/mcp", http_client=client
            ) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await exercise(session)

    asyncio.run(run())


def test_http_requires_secret(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "GAME_OPS_TOKEN"}
    r = subprocess.run(
        [sys.executable, str(SERVER), "--http"],
        env=env,
        capture_output=True,
        timeout=10,
    )
    assert r.returncode != 0 and b"GAME_OPS_TOKEN" in r.stderr


def test_idle_connections_do_not_exhaust_request_capacity(http_server):
    base, _ = http_server
    clients = [httpx2.Client(trust_env=False, timeout=5) for _ in range(12)]
    try:
        for client in clients:
            assert client.get(base + "/healthz").status_code == 200
    finally:
        for client in clients:
            client.close()
