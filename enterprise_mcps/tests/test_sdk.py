"""True MCP Python SDK v2 in-memory and real stdio interoperability tests."""
import asyncio
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path

from enterprise_mcps.common import COMPANIES, contract
from enterprise_mcps.server import create_app

ROOT = Path(__file__).resolve().parents[2]


def data():
    source = 'answer = 1\n'
    return {
        "seum": {
            "analyze_code": {"repository": json.dumps({"path": "src/demo.py",
                "language": "python", "content": "def demo():\n  return 42\n"})},
            "implement_change": {"repository": json.dumps({"path": "src/demo.py", "content": source}),
                "request": json.dumps({"find": "1", "replace": "2",
                    "expected_sha256": hashlib.sha256(source.encode()).hexdigest()})},
            "review_release": {"release_ref": json.dumps({"revision": "abc123",
                "checks": {"ci": "PASS", "tests": "PASS", "security": "PASS",
                           "cost": "PASS", "mobile": "PASS"}})},
        },
        "bonsae": {
            "analyze_design": {"reference": '<html lang="ko"><head><meta name="viewport" content="width=device-width"></head><body><button>Play</button></body></html>'},
            "generate_design_spec": {"brief": json.dumps({"goal": "Game menu",
                "components": [{"name": "Play", "role": "primary button",
                                "states": ["default", "loading", "empty", "error", "disabled"],
                                "mobile_behavior": "responsive full width"}]})},
            "review_visual": {"artifact": json.dumps({"artifact_id": "screen01",
                "viewport": "390px", "observations": [], "screenshot_refs": []})},
        },
        "majung": {
            "research_market": {"question": json.dumps({"question": "Is there demand?",
                "sources": [{"title": "Report", "url": "https://example.com/report",
                    "claim": "Example evidence", "observed_at": "2026-01-01"}]})},
            "analyze_competitors": {"product": json.dumps({"name": "Ours", "price": 100,
                "currency": "USD", "competitors": [{"name": "Peer",
                    "price": 90, "currency": "USD", "source_url": "https://example.com/prices",
                    "observed_at": "2026-01-01"}]})},
            "evaluate_opportunity": {"brief": json.dumps({"name": "Ours", "price": 100,
                "variable_cost": 25, "acquisition_cost": 15,
                "expected_customers": 40, "evidence_urls": []})},
        },
    }


async def verify_client(client, company: str):
    expected = [x["name"] for x in contract(company)["tools"]]
    listed = await client.list_tools()
    observed = [x.name for x in listed.tools]
    if set(observed) != set(expected) or len(observed) != 3:
        raise AssertionError(f"Expected {expected}, got {observed}")
    for name, args in data()[company].items():
        response = await client.call_tool(name, args)
        if response.is_error:
            raise AssertionError(f"Unexpected MCP tool error: {name}: {response}")
        output = response.structured_content
        if isinstance(output, dict) and isinstance(output.get("result"), dict):
            output = output["result"]
        if not isinstance(output, dict):
            raise AssertionError(f"Missing structured result for {name}")
        expected_keys = next(x["output_schema"]["properties"]
            for x in contract(company)["tools"] if x["name"] == name)
        if set(output) != set(expected_keys) or any(not isinstance(x, str) for x in output.values()):
            raise AssertionError(f"Output violates Forge contract: {name}, {output}")
        if name == "analyze_code":
            assert json.loads(output["summary"])["functions"] == 1
        if name == "review_visual":
            assert output["verdict"] == "HOLD_UNINSPECTED"
        if name == "evaluate_opportunity":
            assert output["recommendation"] == "HOLD"
    return {"company": company, "tools": observed, "called": len(expected)}


class SDKTests(unittest.TestCase):
    def test_inmemory_and_stdio(self):
        try:
            import mcp
            from mcp import Client, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            self.skipTest("Official MCP SDK v2 unavailable")

        import importlib.metadata
        self.assertEqual(importlib.metadata.version("mcp").split(".")[0], "2",
                         "Real Python MCP SDK v2 required; no compatibility substitute")

        async def run():
            results = []
            for company in COMPANIES:
                app = create_app(company)
                async with Client(app, raise_exceptions=True) as client:
                    results.append({"transport": "inmemory", **await verify_client(client, company)})
                params = StdioServerParameters(
                    command=sys.executable,
                    args=["-B", "-m", "enterprise_mcps", company],
                    env={"PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"},
                )
                async with Client(stdio_client(params), raise_exceptions=True) as client:
                    results.append({"transport": "stdio", **await verify_client(client, company)})
            return results

        reports = asyncio.run(asyncio.wait_for(run(), timeout=60))
        self.assertEqual(len(reports), 6)
        self.assertEqual(sum(x["called"] for x in reports), 18)


if __name__ == "__main__":
    unittest.main(verbosity=2)
