import json
import os
import unittest
from unittest.mock import patch

from enterprise_mcps import majung, majung_research as research


class Response:
    def __init__(self, body):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, length):
        return self.body[:length]


class Opener:
    def __init__(self, body):
        self.body = body
        self.requests = []
    def open(self, request, timeout):
        self.requests.append(request)
        return Response(self.body)


class MajungLiveTests(unittest.TestCase):
    def test_plain_topic_calls_fixed_public_feed_and_records_provenance(self):
        body = b'<rss><channel><item><title>One</title><link>https://one.example/pricing</link><description>Mini game tools from one</description></item><item><title>Two</title><link>https://two.example/plans</link><description>Mini game tools from two</description></item></channel></rss>'
        opener = Opener(body)
        with patch.dict(os.environ, {}, clear=True), patch.object(research, "build_opener", return_value=opener):
            result = majung.research_market("mini game tools pricing", "KR")
        evidence = json.loads(result["evidence"])
        self.assertEqual(evidence["provider"]["status"], "SUCCESS")
        self.assertEqual(evidence["provider"]["credits_used"], 0)
        self.assertEqual(evidence["distinct_domains"], 2)
        self.assertFalse(evidence["independence_verified"])
        self.assertFalse(evidence["source_content_verified"])
        self.assertIn("www.bing.com/search?", opener.requests[0].full_url)
        self.assertIn("checked_at", evidence["sources"][0])
        self.assertFalse(evidence["sources"][0]["claim_verified"])

    def test_supplied_evidence_does_not_silently_enable_network(self):
        with patch.object(research, "search_market", side_effect=AssertionError("network")):
            result = majung.research_market(json.dumps({"question": "pricing", "sources": []}))
        self.assertEqual(json.loads(result["evidence"])["provider"]["status"], "NOT_REQUESTED")

    def test_failed_feed_is_not_empty_success(self):
        with patch.object(research, "build_opener", return_value=Opener(b"<html>blocked</html>")):
            result = research.search_public_feed("topic")
        self.assertEqual(result["status"], "FAILED")

    def test_irrelevant_provider_response_is_not_research_success(self):
        body = b'<rss><channel><item><title>Adobe Reader</title><link>https://adobe.com/reader</link><description>PDF download</description></item></channel></rss>'
        with patch.object(research, "build_opener", return_value=Opener(body)):
            result = research.search_public_feed("Godot Unity pricing")
        self.assertEqual(result["status"], "LOW_RELEVANCE")
        self.assertEqual(result["sources"][0]["relevance"], "UNCONFIRMED")

    def test_extreme_money_input_cannot_produce_infinite_json(self):
        data = {"name": "ours", "price": 1e-308, "currency": "USD", "competitors": [
            {"name": "peer", "price": 1e308, "currency": "USD", "source_url": "https://example.com/price", "observed_at": "2026-01-01"}]}
        with self.assertRaisesRegex(ValueError, "calculation range"):
            majung.analyze_competitors(json.dumps(data))

    def test_rss_external_entities_rejected(self):
        body = b'<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss><channel/></rss>'
        with patch.object(research, "build_opener", return_value=Opener(body)):
            self.assertEqual(research.search_public_feed("topic")["status"], "FAILED")

    def test_paid_tavily_requires_server_approval_and_does_not_leak_key(self):
        with patch.dict(os.environ, {"TAVILY_API_KEY": "a-private-test-secret", "MAJUNG_SEARCH_ALLOW_CREDIT_USE": "false"}):
            result = research.search_market("topic")
        self.assertEqual(result["status"], "BLOCKED_COST_APPROVAL")
        self.assertNotIn("a-private-test-secret", json.dumps(result))

    def test_ssrf_url_and_dns_guards(self):
        for url in ("http://example.com", "https://127.0.0.1", "https://user:pass@example.com", "https://foo.local", "https://example.com:444", "https://example.com/#x"):
            with self.assertRaises(ValueError):
                research.public_url(url)
        with patch.object(research.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaisesRegex(ValueError, "nonpublic"):
                research._public_address("example.com")

    def test_fetch_does_not_resolve_unallowlisted_hosts(self):
        with patch.dict(os.environ, {"MAJUNG_FETCH_ALLOWED_HOSTS": "official.example"}), patch.object(research, "_public_address", side_effect=AssertionError("DNS")):
            with self.assertRaisesRegex(ValueError, "allowlist"):
                research.observe_source("https://elsewhere.example/pricing")

    def test_direct_source_respects_robots_and_hashes_observed_bytes(self):
        page = b'<html><title>Verified publisher page</title><p>Pricing schedule</p><script>secret</script></html>'
        with patch.dict(os.environ, {"MAJUNG_FETCH_ALLOWED_HOSTS": "official.example"}), patch.object(research, "_public_address", return_value="93.184.216.34"), patch.object(research, "_get", side_effect=[(b"User-agent: *\nAllow: /", "text/plain"), (page, "text/html")]):
            result = research.observe_source("https://official.example/pricing")
        self.assertTrue(result["retrieval_verified"])
        self.assertFalse(result["claim_verified"])
        self.assertEqual(len(result["sha256"]), 64)
        self.assertNotIn("secret", result["claim"])
        with patch.dict(os.environ, {"MAJUNG_FETCH_ALLOWED_HOSTS": "official.example"}), patch.object(research, "_public_address", return_value="93.184.216.34"), patch.object(research, "_get", return_value=(b"User-agent: *\nDisallow: /", "text/plain")) as getter:
            with self.assertRaisesRegex(ValueError, "robots"):
                research.observe_source("https://official.example/pricing")
            self.assertEqual(getter.call_count, 1)

    def test_unknown_price_stays_unknown_and_annual_units_normalize(self):
        data = {"name": "ours", "price": 10, "currency": "USD", "period": "month", "competitors": [
            {"name": "annual", "price": 120, "currency": "USD", "period": "year", "source_url": "https://a.example/pricing", "observed_at": "2026-01-01"},
            {"name": "unknown", "price": None, "currency": "USD", "source_url": "https://b.example/pricing", "observed_at": "2026-01-01"}]}
        rows = json.loads(majung.analyze_competitors(json.dumps(data))["competitors"])["rows"]
        self.assertEqual(rows[0]["price"], 10)
        self.assertEqual(rows[0]["price_status"], "CALLER_ASSUMPTION")
        self.assertEqual(rows[1]["price_status"], "UNKNOWN")
        self.assertIsNone(rows[1]["delta_percent_vs_ours"])

    def test_free_target_and_competitors_keep_zero_and_undefined_ratios(self):
        data = {"name": "Free target", "price": 0, "currency": "USD", "competitors": [
            {"name": "Godot", "price": 0, "currency": "USD", "source_url": "https://godotengine.org/license/", "observed_at": "2026-01-01"},
            {"name": "Paid peer", "price": 10, "currency": "USD", "source_url": "https://example.com/pricing", "observed_at": "2026-01-01"}]}
        result = majung.analyze_competitors(json.dumps(data))
        rows = json.loads(result["competitors"])["rows"]
        self.assertEqual(rows[0]["price"], 0)
        self.assertTrue(all(row["delta_percent_vs_ours"] is None for row in rows))
        self.assertTrue(all("zero" in row["delta_percent_undefined_reason"] for row in rows))
        data["price"] = 10
        data["competitors"] = data["competitors"][:1]
        result = majung.analyze_competitors(json.dumps(data))
        self.assertEqual(json.loads(result["competitors"])["rows"][0]["delta_percent_vs_ours"], -100)
        differentiation = json.loads(result["differentiation"])
        self.assertIsNone(differentiation["our_delta_percent_vs_median"])
        self.assertIn("zero", differentiation["median_delta_undefined_reason"])

    def test_break_even_and_explicit_scenarios_do_not_invent_demand(self):
        assumptions = {"price": 100, "variable_cost": 25, "acquisition_cost": 10, "expected_customers": 10}
        data = {"name": "ours", **assumptions, "fixed_cost": 1000, "scenarios": {"optimistic": {**assumptions, "expected_customers": 100}}}
        result = majung.evaluate_opportunity(json.dumps(data))
        risks = json.loads(result["risks"])
        self.assertEqual(result["recommendation"], "HOLD")
        self.assertEqual(risks["scenario"]["break_even_customers"], 16)
        self.assertEqual(risks["scenario"]["projected_after_fixed_cost"], -350)
        self.assertEqual(risks["scenarios"]["pessimistic"]["status"], "MISSING_ASSUMPTIONS")
        self.assertFalse(risks["spend_authorized"])
        self.assertFalse(risks["initial_experiment"]["executed"])


if __name__ == "__main__":
    unittest.main()
