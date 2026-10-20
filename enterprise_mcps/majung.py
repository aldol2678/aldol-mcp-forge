"""MAJUNG market intelligence: only supplied evidence; no search, claims or spend."""
from datetime import date, datetime, timezone
from urllib.parse import urlsplit
from .common import json_input, string, finite_number, source_url, observation_date, payload

def research_market(question: str, region: str | None = None) -> dict[str, str]:
    data = json_input(question, "question", {"question", "sources"})
    topic = string(data.get("question"), "question", max_length=300)
    area = string(region, "region", max_length=100) if region is not None else "unspecified"
    sources = data.get("sources", [])
    if not isinstance(sources, list) or len(sources) > 20:
        raise ValueError("sources must be an array of up to 20 supplied records")
    results = []
    hosts = set()
    stale = []
    today = datetime.now(timezone.utc).date()
    for i, source in enumerate(sources):
        if not isinstance(source, dict) or set(source) != {"title", "url", "claim", "observed_at"}:
            raise ValueError("Source needs title/url/claim/observed_at")
        url = source_url(source["url"])
        observed = observation_date(source["observed_at"])
        host = urlsplit(url).hostname.lower()
        hosts.add(host)
        if (today - date.fromisoformat(observed)).days > 365:
            stale.append(url)
        results.append({"title": string(source["title"], "source title", max_length=180),
                        "url": url, "claim": string(source["claim"], "claim", max_length=350),
                        "observed_at": observed, "host": host})
    uncertainties = []
    if not results:
        uncertainties.append("No dated sources supplied; live market research not performed")
    if len(hosts) < 2:
        uncertainties.append("Fewer than two independent source domains; corroboration needed")
    if stale:
        uncertainties.append("Some supplied observations are older than one year")
    uncertainties.append("Source contents and claims are user-supplied, not independently fetched or verified")
    return {"evidence": payload({"question": topic, "region": area, "sources": results,
                                 "independent_domains": len(hosts), "source_content_verified": False}),
            "uncertainties": payload(uncertainties)}

def analyze_competitors(product: str) -> dict[str, str]:
    data = json_input(product, "product", {"name", "price", "currency", "competitors"})
    name = string(data.get("name"), "name", max_length=100)
    price = finite_number(data.get("price"), "price", zero=False)
    currency = string(data.get("currency"), "currency", max_length=10)
    competitors = data.get("competitors")
    if not isinstance(competitors, list) or not 1 <= len(competitors) <= 20:
        raise ValueError("competitors must contain 1..20 comparable prices")
    rows = []
    for item in competitors:
        if not isinstance(item, dict) or set(item) != {"name", "price", "currency", "source_url", "observed_at"}:
            raise ValueError("Each competitor requires dated price/source/currency")
        label = string(item["name"], "competitor name", max_length=100)
        peer_currency = string(item["currency"], "competitor currency", max_length=10)
        if peer_currency != currency:
            raise ValueError("Mixed currencies are not comparable without verified FX conversion")
        peer_price = finite_number(item["price"], "competitor price", zero=False)
        url = source_url(item["source_url"])
        obs = observation_date(item["observed_at"])
        rows.append({"name": label, "price": peer_price, "currency": currency,
                     "delta_percent_vs_ours": round((peer_price / price - 1) * 100, 2),
                     "source_url": url, "observed_at": obs, "source_verified": False})
    rows.sort(key=lambda p: (p["price"], p["name"]))
    median = sorted(r["price"] for r in rows)
    mid = len(median) // 2
    median_price = median[mid] if len(median) % 2 else (median[mid - 1] + median[mid]) / 2
    return {"competitors": payload({"target": name, "target_price": price, "currency": currency, "rows": rows}),
            "differentiation": payload({"type": "price_position_only", "market_median": median_price,
                "our_delta_percent_vs_median": round((price / median_price - 1) * 100, 2),
                "unverified_claims": "All prices and sources provided by caller; no value-feature comparison"})}

def evaluate_opportunity(brief: str) -> dict[str, str]:
    data = json_input(brief, "brief",
                      {"name", "price", "variable_cost", "acquisition_cost", "expected_customers", "evidence_urls"})
    name = string(data.get("name"), "name", max_length=120)
    price = finite_number(data.get("price"), "price", zero=False)
    variable = finite_number(data.get("variable_cost"), "variable_cost")
    acquisition = finite_number(data.get("acquisition_cost"), "acquisition_cost")
    customers = finite_number(data.get("expected_customers"), "expected_customers")
    if not customers.is_integer() or customers > 1_000_000_000:
        raise ValueError("expected_customers must be a bounded whole number")
    evidence = data.get("evidence_urls", [])
    if not isinstance(evidence, list) or len(evidence) > 20:
        raise ValueError("evidence_urls must be a list of up to 20 HTTPS URLs")
    urls = [source_url(x) for x in evidence]
    unit_contribution = price - variable - acquisition
    projected = unit_contribution * customers
    warnings = ["Demand/price/cost inputs are unverified scenario assumptions",
                "No decision grants budget, marketing campaign, launch or payment authority"]
    if not urls:
        warnings.append("No evidence URLs provided")
    elif len({urlsplit_host(x) for x in urls}) < 2:
        warnings.append("Evidence from fewer than two distinct domains")
    recommendation = "NO-GO" if unit_contribution < 0 else "HOLD"
    if unit_contribution == 0:
        warnings.append("Unit contribution is zero before fixed costs")
    if unit_contribution > 0:
        warnings.append("Positive unit contribution alone cannot validate customer demand or fixed-cost break-even")
    return {"recommendation": recommendation,
            "risks": payload({"name": name, "scenario": {"price": price, "variable_cost": variable,
                "acquisition_cost": acquisition, "expected_customers": int(customers),
                "unit_contribution": round(unit_contribution, 2),
                "projected_pre_fixed_cost_contribution": round(projected, 2)},
                "evidence_urls_unverified": urls, "warnings": warnings,
                "decision_is_advisory": True, "launch_authorized": False})}

def urlsplit_host(url):
    return urlsplit(url).hostname.lower()
