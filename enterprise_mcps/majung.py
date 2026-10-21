"""MAJUNG market intelligence: only supplied evidence; no search, claims or spend."""
from datetime import date, datetime, timezone
from urllib.parse import urlsplit
from .common import json_input, string, finite_number, source_url, observation_date, payload

def _amount(value, field, *, zero=True):
    amount = finite_number(value, field, zero=zero)
    if amount > 1e15 or 0 < amount < 1e-8:
        raise ValueError(field + " is outside supported economic calculation range")
    return amount

def research_market(question: str, region: str | None = None) -> dict[str, str]:
    """Collect live provider evidence or triage explicitly supplied observations."""
    import json
    import hashlib
    from . import majung_research as research
    text = string(question, "question", max_length=4096)
    if text.lstrip().startswith("{"):
        data = json_input(text, "question", {"question", "sources", "live", "source_urls"})
        live = data.get("live", False)
    else:
        data = {"question": text, "sources": []}
        live = True
    if not isinstance(live, bool):
        raise ValueError("live must be boolean")
    topic = string(data.get("question"), "question", max_length=300)
    area = string(region, "region", max_length=100) if region is not None else "unspecified"
    sources = data.get("sources", [])
    urls = data.get("source_urls", [])
    if not isinstance(sources, list) or len(sources) > 20:
        raise ValueError("sources must be an array of up to 20 supplied records")
    if not isinstance(urls, list) or len(urls) > 5:
        raise ValueError("source_urls must contain up to 5 explicit source URLs")
    results, stale, failures = [], [], []
    today = datetime.now(timezone.utc).date()
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"title", "url", "claim", "observed_at"}:
            raise ValueError("Source needs title/url/claim/observed_at")
        url = source_url(source["url"])
        research.public_url(url)
        observed = observation_date(source["observed_at"])
        if (today - date.fromisoformat(observed)).days > 365:
            stale.append(url)
        results.append({"title": string(source["title"], "source title", max_length=180),
                        "url": url, "claim": string(source["claim"], "claim", max_length=350),
                        "observed_at": observed, "host": urlsplit(url).hostname.lower(),
                        "method": "caller_supplied", "retrieval_verified": False, "source_content_verified": False,
                        "claim_verified": False, "published_at": None,
                        "trust": "unverified supplied observation"})
    provider = research.search_market(topic, area) if live else {
        "status": "NOT_REQUESTED", "provider": None, "sources": [], "credits_used": 0}
    results += provider.get("sources", [])
    for url in urls:
        source_url(url)
        try:
            results.append(research.observe_source(url))
        except (ValueError, OSError) as exc:
            failures.append({"url": url, "status": "UNVERIFIED", "reason": str(exc)[:180]})
    unique = []
    seen = set()
    for row in results:
        if row["url"] not in seen:
            seen.add(row["url"])
            unique.append(row)
    hosts = {row["host"] for row in unique}
    uncertainties = []
    if not unique:
        uncertainties.append("No dated sources available")
    if len(hosts) < 2:
        uncertainties.append("Fewer than two distinct source domains; corroboration needed")
    uncertainties.append("Distinct domains do not establish editorial or ownership independence")
    if stale:
        uncertainties.append("Some supplied observations are older than one year")
    if any(row["method"] == "caller_supplied" for row in unique):
        uncertainties.append("Caller-supplied claims are not independently fetched or verified")
    if live and provider["status"] != "SUCCESS":
        uncertainties.append("Live search " + provider["status"] + ": " + provider.get("reason", "insufficient results"))
    uncertainties += ["Search snippets and publisher text are observations, not verified market facts",
                      "Conflicting evidence and source independence require contextual review"]
    checked = research.timestamp()
    evidence = {"question": topic, "region": area, "sources": unique,
                "independent_domains": len(hosts), "distinct_domains": len(hosts),
                "independence_verified": False,
                "source_content_verified": False,
                "source_content_verification_scope": "Per-source retrieval flags only; independent corroboration is not established",
                "provider": {k:v for k,v in provider.items() if k != "sources"},
                "source_failures": failures, "checked_at": checked,
                "analysis": {"type": "evidence_collection", "market_conclusion": "NOT_ESTABLISHED"},
                "conflicts": {"status": "NOT_AUTOMATICALLY_RESOLVED", "items": []},
                "unverified_claims": [row["url"] for row in unique if not row.get("claim_verified")]}
    evidence["report_id"] = "majung-" + hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()[:16]
    return {"evidence": payload(evidence), "uncertainties": payload(uncertainties)}

def analyze_competitors(product: str) -> dict[str, str]:
    """Compare explicit price assumptions; optional live discovery is evidence only."""
    from . import majung_research as research
    import re
    data = json_input(product, "product", {"name", "price", "currency", "competitors", "period", "live"})
    name = string(data.get("name"), "name", max_length=100)
    price = _amount(data.get("price"), "price")
    currency = string(data.get("currency"), "currency", max_length=10).upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("currency must be a three-letter ISO currency code")
    period = data.get("period", "unspecified")
    if period not in ("unspecified", "one_time", "month", "year"):
        raise ValueError("period must be one_time, month, year or unspecified")
    live = data.get("live", False)
    if not isinstance(live, bool):
        raise ValueError("live must be boolean")
    competitors = data.get("competitors", [])
    if not isinstance(competitors, list) or len(competitors) > 20 or (not competitors and not live):
        raise ValueError("competitors must contain 1..20 comparable prices, or request live discovery")
    rows = []
    for item in competitors:
        required = {"name", "price", "currency", "source_url", "observed_at"}
        if not isinstance(item, dict) or not required <= set(item) or set(item) - (required | {"period", "features", "billing", "target_customer", "positioning"}):
            raise ValueError("Each competitor requires dated price/source/currency")
        label = string(item["name"], "competitor name", max_length=100)
        peer_currency = string(item["currency"], "competitor currency", max_length=10).upper()
        if peer_currency != currency:
            raise ValueError("Mixed currencies are not comparable without verified FX conversion")
        peer_price = _amount(item["price"], "competitor price") if item["price"] is not None else None
        peer_period = item.get("period", period)
        if peer_period not in ("unspecified", "one_time", "month", "year"):
            raise ValueError("Invalid competitor price period")
        original_price = peer_price
        normalization = None
        if peer_period != period:
            if {peer_period, period} == {"month", "year"}:
                if peer_price is not None:
                    peer_price = peer_price / 12 if peer_period == "year" else peer_price * 12
                normalization = "annual / 12" if peer_period == "year" else "monthly * 12"
            else:
                raise ValueError("Mixed billing units cannot be compared")
        url = source_url(item["source_url"])
        research.public_url(url)
        obs = observation_date(item["observed_at"])
        row = {"name": label, "price": peer_price, "currency": currency, "period": period,
               "original_price": original_price, "original_period": peer_period, "normalization": normalization,
               "delta_percent_vs_ours": round((peer_price / price - 1) * 100, 2) if peer_price is not None and price > 0 else None,
               "delta_percent_undefined_reason": "Target price is zero; relative percentage is undefined" if price == 0 else "Competitor price is unknown" if peer_price is None else None,
               "source_url": url, "observed_at": obs, "source_verified": False,
               "price_status": "CALLER_ASSUMPTION" if peer_price is not None else "UNKNOWN"}
        for field in ("features", "billing", "target_customer", "positioning"):
            if field in item:
                row[field] = string(item[field], field, max_length=300)
        rows.append(row)
    rows.sort(key=lambda p: (p["price"] is None, p["price"] or 0, p["name"]))
    valid_prices = sorted(r["price"] for r in rows if r["price"] is not None)
    mid = len(valid_prices) // 2
    median_price = (valid_prices[mid] if len(valid_prices) % 2 else (valid_prices[mid - 1] + valid_prices[mid]) / 2) if valid_prices else None
    provider = research.search_market(name + " competitors pricing") if live else None
    live_candidates = []
    if provider:
        for row in provider.get("sources", []):
            live_candidates.append({**row, "price": None, "price_status": "UNKNOWN",
                                    "pricing_mentions_unverified": re.findall(r"(?:USD|EUR|KRW|\$|€|₩)\s?\d[\d,.]*(?:\s*/\s*(?:mo|month|year))?", row["claim"])[:8]})
    return {"competitors": payload({"target": name, "target_price": price, "currency": currency,
                                     "period": period, "rows": rows, "live_candidates": live_candidates,
                                     "provider_status": provider.get("status") if provider else "NOT_REQUESTED"}),
            "differentiation": payload({"type": "price_position_only", "market_median": median_price,
                "our_delta_percent_vs_median": round((price / median_price - 1) * 100, 2) if median_price else None,
                "median_delta_undefined_reason": "Median competitor price is zero; relative percentage is undefined" if median_price == 0 else "No known competitor prices" if median_price is None else None,
                "unverified_claims": "Supplied prices/features are assumptions; live snippets require product/tier/unit/date confirmation",
                "positioning": "Requires contextual feature and customer evidence; no automatic superiority claim"})}

def evaluate_opportunity(brief: str) -> dict[str, str]:
    """Calculate stated scenarios; do not invent customer demand or authorize spend."""
    import math
    data = json_input(brief, "brief", {"name", "price", "variable_cost", "acquisition_cost", "expected_customers",
                                      "evidence_urls", "fixed_cost", "currency", "scenarios", "experiment", "customer"})
    name = string(data.get("name"), "name", max_length=120)
    fixed = _amount(data.get("fixed_cost", 0), "fixed_cost")
    currency = string(data.get("currency", "unspecified"), "currency", max_length=20)
    def scenario(row, label):
        if not isinstance(row, dict) or set(row) - {"price", "variable_cost", "acquisition_cost", "expected_customers", "fixed_cost"}:
            raise ValueError("Scenario must contain only explicit economic assumptions")
        values = {key: _amount(row.get(key), key, zero=(key != "price")) for key in
                  ("price", "variable_cost", "acquisition_cost", "expected_customers")}
        customers = values["expected_customers"]
        if not customers.is_integer() or customers > 1_000_000_000:
            raise ValueError("expected_customers must be a bounded whole number")
        fixed_cost = _amount(row.get("fixed_cost", fixed), "fixed_cost")
        contribution = values["price"] - values["variable_cost"] - values["acquisition_cost"]
        projected = contribution * customers
        derived = (contribution, projected, projected - fixed_cost)
        if not all(math.isfinite(value) for value in derived):
            raise ValueError("Economic calculation overflow")
        return {**values, "expected_customers": int(customers), "label": label, "fixed_cost": fixed_cost,
                "unit_contribution": round(contribution, 2), "unit_contribution_ratio": round(contribution / values["price"], 6),
                "projected_pre_fixed_cost_contribution": round(projected, 2),
                "projected_after_fixed_cost": round(projected - fixed_cost, 2),
                "break_even_customers": math.ceil(fixed_cost / contribution) if contribution > 0 else None,
                "assumptions_verified": False}
    base = scenario({key: data[key] for key in ("price", "variable_cost", "acquisition_cost", "expected_customers") if key in data}, "base")
    scenarios = data.get("scenarios", {})
    if not isinstance(scenarios, dict) or set(scenarios) - {"optimistic", "pessimistic"}:
        raise ValueError("scenarios may specify explicit optimistic and pessimistic assumptions")
    output_scenarios = {"base": base}
    for label in ("optimistic", "pessimistic"):
        output_scenarios[label] = scenario(scenarios[label], label) if label in scenarios else {"status": "MISSING_ASSUMPTIONS"}
    evidence = data.get("evidence_urls", [])
    if not isinstance(evidence, list) or len(evidence) > 20:
        raise ValueError("evidence_urls must be a list of up to 20 HTTPS URLs")
    urls = [source_url(x) for x in evidence]
    from .majung_research import public_url
    for url in urls:
        public_url(url)
    warnings = ["Demand/price/cost inputs are unverified scenario assumptions",
                "No decision grants budget, marketing campaign, launch, investment or payment authority",
                "Fixed cost excludes any unstated costs; tax/refund/payment fees must be included in supplied assumptions"]
    if not urls:
        warnings.append("No evidence URLs provided")
    elif len({urlsplit_host(x) for x in urls}) < 2:
        warnings.append("Evidence from fewer than two distinct domains")
    if base["unit_contribution"] <= 0:
        warnings.append("Nonpositive unit contribution cannot cover positive fixed costs")
    else:
        warnings.append("Positive unit contribution alone does not establish demand")
    experiment = data.get("experiment")
    if experiment is not None:
        experiment = string(experiment, "experiment", max_length=500)
    else:
        experiment = "Interview target customers and test a no-payment interest form; predefine demand and cost thresholds before any spend"
    customer = data.get("customer", "Not specified; customer definition is required before demand testing")
    customer = string(customer, "customer", max_length=300)
    return {"recommendation": "NO-GO" if base["unit_contribution"] < 0 else "HOLD",
            "risks": payload({"name": name, "currency": currency, "customer": customer, "scenario": base,
                "scenarios": output_scenarios, "initial_experiment": {"proposal": experiment, "executed": False},
                "evidence_urls_unverified": urls, "warnings": warnings,
                "decision_is_advisory": True, "launch_authorized": False, "spend_authorized": False})}

def urlsplit_host(url):
    return urlsplit(url).hostname.lower()
