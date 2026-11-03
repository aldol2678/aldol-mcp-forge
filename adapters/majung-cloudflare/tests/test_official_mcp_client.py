"""Opt-in real MCP Python SDK 2.0 QA test against isolated MAJUNG Preview.

Never runs automatically or against production. Requires an explicitly
provided synthetic bearer and the exact isolated QA URL.
Usage:
 MAJUNG_QA_BEARER='<test-only token>' python tests/test_official_mcp_client.py
The QA Preview must be temporarily enabled by an authorized operator.
"""
import asyncio
import json
import os
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

URL = "https://majung-offline-smoke-20261103-aldol-majung-cf-qa.aldol-lab.workers.dev/mcp"
VERSION = "2026-07-28"

async def check():
    token = os.getenv("MAJUNG_QA_BEARER", "")
    if not token.startswith("test-only-") or len(token) < 40:
        raise RuntimeError("An explicit isolated synthetic test bearer is required")
    passed = []
    async with httpx2.AsyncClient(
        headers={"Authorization": "Bearer " + token}, timeout=20
    ) as http:
        async with Client(streamable_http_client(URL, http_client=http), mode="auto") as client:
            assert client.protocol_version == VERSION
            passed.append("official SDK modern protocol")
            names = [tool.name for tool in (await client.list_tools()).tools]
            assert names == ["research_market", "analyze_competitors", "evaluate_opportunity"]
            passed.append("official SDK tools/list")
            market = await client.call_tool("research_market", {"question": json.dumps({
                "question": "test market", "sources": [], "live": False
            })})
            assert not market.is_error
            assert json.loads(market.structured_content["evidence"])["provider"]["status"] == "NOT_REQUESTED"
            passed.append("official SDK research_market offline")
            competitor = await client.call_tool("analyze_competitors", {"product": json.dumps({
                "name": "ours", "price": 0, "currency": "USD", "competitors": [{
                    "name": "peer", "price": None, "currency": "USD",
                    "source_url": "https://example.com/price", "observed_at": "2026-01-01"
                }]
            })})
            assert not competitor.is_error
            assert json.loads(competitor.structured_content["competitors"])["rows"][0]["price_status"] == "UNKNOWN"
            passed.append("official SDK analyze_competitors")
            opportunity = await client.call_tool("evaluate_opportunity", {"brief": json.dumps({
                "name": "pilot", "price": 100, "variable_cost": 20,
                "acquisition_cost": 10, "expected_customers": 10, "fixed_cost": 1000
            })})
            assert not opportunity.is_error and opportunity.structured_content["recommendation"] == "HOLD"
            passed.append("official SDK evaluate_opportunity")
            live = await client.call_tool("research_market", {"question": "live market research"})
            assert live.is_error
            passed.append("live search remains disabled")

        headers = {"MCP-Protocol-Version": VERSION, "Mcp-Method": "tools/list",
                   "Accept": "application/json, text/event-stream"}
        meta = {"io.modelcontextprotocol/protocolVersion": VERSION,
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": {"name": "MAJUNG-QA", "version": "1.0"}}
        async def rpc(method="tools/list", params=None, extra_headers=None):
            body = {"jsonrpc": "2.0", "id": "qa", "method": method,
                    "params": {"_meta": meta, **(params or {})}}
            r = await http.post(URL, json=body, headers={**headers, **(extra_headers or {})})
            return r.status_code, r.json()

        status, obj = await rpc("server/discover", extra_headers={"Mcp-Method": "server/discover"})
        assert status == 200 and obj["result"]["supportedVersions"] == [VERSION]
        assert obj["result"]["resultType"] == "complete"
        passed.append("modern server/discover")
        status, obj = await rpc()
        assert status == 200 and obj["result"]["cacheScope"] == "private" and obj["result"]["ttlMs"] == 0
        passed.append("cacheable tools/list shape")
        status, obj = await rpc(extra_headers={"Mcp-Method": "tools/call"})
        assert status == 400 and obj["error"]["code"] == -32020
        passed.append("method mirror mismatch denied")
        status, obj = await rpc(extra_headers={"MCP-Protocol-Version": "2025-11-25"})
        assert status == 400 and obj["error"]["code"] == -32020
        passed.append("protocol header mismatch denied")
        status, obj = await rpc(extra_headers={"Origin": "https://untrusted.example"})
        assert status == 403
        passed.append("origin rejected")
    print(json.dumps({"result": "PASS", "checks": passed}, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(check())
