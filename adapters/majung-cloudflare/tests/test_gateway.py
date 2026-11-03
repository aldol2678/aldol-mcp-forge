"""Local offline contract tests. Does not test actual Cloudflare Python runtime."""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "src"))

from prepare import prepare
prepare()
from gateway import TOOL_SPECS, invoke_tool

class GatewayTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual([t["name"] for t in TOOL_SPECS],
                         ["research_market", "analyze_competitors", "evaluate_opportunity"])

    def test_offline_research(self):
        q = {"question": "Comparison", "sources": [], "live": False}
        out = invoke_tool("research_market", {"question": json.dumps(q)})
        self.assertEqual(set(out), {"evidence", "uncertainties"})
        self.assertEqual(json.loads(out["evidence"])["provider"]["status"], "NOT_REQUESTED")

    def test_market_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "blocked"):
            invoke_tool("research_market", {"question": "market research"})
        with self.assertRaisesRegex(ValueError, "Direct source"):
            invoke_tool("research_market", {"question": json.dumps({
                "question": "market", "live": False,
                "source_urls": ["https://example.com/pricing"]})})

    def test_competitor_and_unknown(self):
        data = {"name": "ours", "price": 0, "currency": "USD",
                "competitors": [{"name": "peer", "price": None, "currency": "USD",
                                "observed_at": "2026-01-01",
                                "source_url": "https://example.com/pricing"}]}
        out = invoke_tool("analyze_competitors", {"product": json.dumps(data)})
        self.assertEqual(set(out), {"competitors", "differentiation"})
        self.assertEqual(json.loads(out["competitors"])["rows"][0]["price_status"], "UNKNOWN")

    def test_opportunity_hold(self):
        data = {"name": "pilot", "price": 100, "variable_cost": 20,
                "acquisition_cost": 10, "expected_customers": 10, "fixed_cost": 1000}
        out = invoke_tool("evaluate_opportunity", {"brief": json.dumps(data)})
        self.assertEqual(out["recommendation"], "HOLD")
        self.assertFalse(json.loads(out["risks"])["spend_authorized"])

    def test_invalid_tools(self):
        with self.assertRaises(ValueError):
            invoke_tool("delete_service", {})
        with self.assertRaises(ValueError):
            invoke_tool("evaluate_opportunity", {"brief": "{}", "shell": "rm -rf /"})

if __name__ == "__main__":
    unittest.main()
