"""Official Python MCP SDK test against isolated MAJUNG QA relay -> QA backend.

Requires temporary QA route enablement and *synthetic* QA gate value.
Does not deploy, update existing Studio, or enable live search.
Install mcp==2.0.0, httpx2, and set MAJUNG_QA_RELAY_GATE in the shell.
"""
import asyncio
import json
import os

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

URL = "https://aldol-majung-relay-qa.aldol-lab.workers.dev/mcp"
NAMES = ["research_market", "analyze_competitors", "evaluate_opportunity"]


async def main():
    gate = os.getenv("MAJUNG_QA_RELAY_GATE", "")
    if not gate.startswith("qa-relay-gate-test-only-") or len(gate) < 35:
        raise RuntimeError("Use only an explicitly provided synthetic QA gate")
    checks = []
    async with httpx2.AsyncClient(
        headers={"x-qa-relay-authorization": gate}, timeout=30
    ) as http:
        async with Client(streamable_http_client(URL, http_client=http), mode="auto") as client:
            assert client.protocol_version == "2026-07-28"
            checks.append("official SDK connected to QA relay")
            tools = await client.list_tools()
            assert [t.name for t in tools.tools] == NAMES
            checks.append("tools/list exactly three")
            market = await client.call_tool("research_market", {
                "question": json.dumps({"question": "QA offline research", "sources": [], "live": False})
            })
            assert not market.is_error
            assert json.loads(market.structured_content["evidence"])["provider"]["status"] == "NOT_REQUESTED"
            checks.append("offline research through relay")
            competitors = await client.call_tool("analyze_competitors", {
                "product": json.dumps({
                    "name": "ours", "price": 0, "currency": "USD",
                    "competitors": [{"name": "peer", "price": None, "currency": "USD",
                                     "observed_at": "2026-01-01",
                                     "source_url": "https://example.com/pricing"}]
                })
            })
            assert not competitors.is_error
            assert json.loads(competitors.structured_content["competitors"])["rows"][0]["price_status"] == "UNKNOWN"
            checks.append("competitors through relay")
            opportunity = await client.call_tool("evaluate_opportunity", {
                "brief": json.dumps({
                    "name": "pilot", "price": 100, "variable_cost": 20,
                    "acquisition_cost": 10, "expected_customers": 10, "fixed_cost": 1000
                })
            })
            assert not opportunity.is_error
            assert opportunity.structured_content["recommendation"] == "HOLD"
            checks.append("opportunity through relay")
            live = await client.call_tool("research_market", {"question": "live source prices"})
            assert live.is_error
            checks.append("live search rejected")
    print(json.dumps({"passed":len(checks),"total":len(checks),"checks":checks},ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
