"""MAJUNG's reviewed Python business logic behind an explicit Cloudflare boundary.

The original enterprise_mcps.majung is copied without changes by prepare.py.
No paid provider keys or arbitrary URL access are enabled by this adapter.
"""
import json
from enterprise_mcps import majung

TOOL_SPECS = [
    {"name": "research_market", "description": "Gather dated market evidence; live discovery requires verified backend enablement.",
     "inputSchema": {"type": "object", "additionalProperties": False, "required": ["question"],
       "properties": {"question": {"type": "string", "maxLength": 262144}, "region": {"type": "string", "maxLength": 262144}}}},
    {"name": "analyze_competitors", "description": "Compare documented prices with honest UNKNOWN values and billing units.",
     "inputSchema": {"type": "object", "additionalProperties": False, "required": ["product"],
       "properties": {"product": {"type": "string", "maxLength": 262144}}}},
    {"name": "evaluate_opportunity", "description": "Compute caller-supplied unit economics; recommendations never authorize spending.",
     "inputSchema": {"type": "object", "additionalProperties": False, "required": ["brief"],
       "properties": {"brief": {"type": "string", "maxLength": 262144}}}}
]
FUNCTIONS = {
    "research_market": majung.research_market,
    "analyze_competitors": majung.analyze_competitors,
    "evaluate_opportunity": majung.evaluate_opportunity,
}
OUTPUT_KEYS = {
    "research_market": {"evidence", "uncertainties"},
    "analyze_competitors": {"competitors", "differentiation"},
    "evaluate_opportunity": {"recommendation", "risks"},
}

def invoke_tool(name, arguments, *, allow_live=False):
    spec = next((s for s in TOOL_SPECS if s["name"] == name), None)
    if spec is None:
        raise ValueError("Unknown MAJUNG tool")
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a JSON object")
    props = spec["inputSchema"]["properties"]
    if set(arguments) - set(props) or not set(spec["inputSchema"]["required"]) <= set(arguments):
        raise ValueError("Unsupported or missing tool arguments")
    for value in arguments.values():
        if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 262144):
            raise ValueError("Tool arguments must be bounded strings")
    if name == "research_market":
        raw = arguments["question"].lstrip()
        if raw.startswith("{"):
            request = json.loads(raw)
            if not isinstance(request, dict):
                raise ValueError("Research input must be an object")
            # Original direct fetch uses DNS-pin/robots on CPython. It has NOT
            # been proven equivalent in the Workers/Pyodide runtime.
            if request.get("source_urls"):
                raise ValueError("Direct source collection is blocked pending Workers security verification")
            needs_live = request.get("live", False)
        else:
            needs_live = True
        if needs_live and not allow_live:
            raise ValueError("Live market search is blocked until Cloudflare runtime verification")
    elif name == "analyze_competitors":
        data = json.loads(arguments["product"])
        if not isinstance(data, dict):
            raise ValueError("Competitor input must be an object")
        if data.get("live", False) and not allow_live:
            raise ValueError("Live competitor discovery is blocked until Cloudflare runtime verification")
    result = FUNCTIONS[name](**arguments)
    if not isinstance(result, dict) or set(result) != OUTPUT_KEYS[name] or any(not isinstance(x, str) for x in result.values()):
        raise ValueError("Implementation output differs from the MAJUNG contract")
    return result
