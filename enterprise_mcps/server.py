"""Nine real, locally bounded specialist handlers exposed as three separate MCP servers.

Each tool is mapped to a reviewed function, not generated arbitrary Python.
No external HTTP, shell commands, filesystem mutations, AI model calls, or deploys.
"""
from __future__ import annotations
from typing import Any

from . import seum, bonsae, majung
from .common import COMPANIES, contract, string, verify_output

FUNCTIONS = {
    "seum": {"analyze_code": seum.analyze_code,
             "implement_change": seum.implement_change,
             "review_release": seum.review_release},
    "bonsae": {"analyze_design": bonsae.analyze_design,
               "generate_design_spec": bonsae.generate_design_spec,
               "review_visual": bonsae.review_visual},
    "majung": {"research_market": majung.research_market,
               "analyze_competitors": majung.analyze_competitors,
               "evaluate_opportunity": majung.evaluate_opportunity},
}

def invoke(company: str, name: str, arguments: dict[str, Any]) -> dict[str, str]:
    if company not in COMPANIES or name not in FUNCTIONS[company]:
        raise ValueError("Unknown specialist tool")
    tool = next(t for t in contract(company)["tools"] if t["name"] == name)
    inputs = {f["name"]: f for f in tool["inputs"]}
    if set(arguments) - set(inputs):
        raise ValueError("Unknown tool input")
    for field in tool["inputs"]:
        if field["required"] and field["name"] not in arguments:
            raise ValueError("Missing input: " + field["name"])
    for key, value in arguments.items():
        if value is not None:
            string(value, key, max_length=4096)
    result = FUNCTIONS[company][name](**arguments)
    return verify_output(company, name, result)

def create_app(company: str):
    from mcp.server import MCPServer
    if company not in COMPANIES:
        raise ValueError("Unknown specialist company")
    expected = {t["name"] for t in contract(company)["tools"]}
    if set(FUNCTIONS[company]) != expected:
        raise ValueError("Specialist implementation registry does not match Forge contract")
    app = MCPServer("aldol-" + company + "-mcp")

    if company == "seum":
        @app.tool()
        def analyze_code(repository: str, focus: str | None = None) -> dict[str, str]:
            """Inspect caller-provided Python/JSON content without executing or fetching a repository."""
            return invoke(company, "analyze_code", {"repository": repository, "focus": focus})
        @app.tool()
        def implement_change(repository: str, request: str) -> dict[str, str]:
            """Generate an exact, checksum-guarded source diff, never apply it."""
            return invoke(company, "implement_change", {"repository": repository, "request": request})
        @app.tool()
        def review_release(release_ref: str) -> dict[str, str]:
            """Evaluate supplied CI/security/cost/mobile evidence; no release authorization."""
            return invoke(company, "review_release", {"release_ref": release_ref})

    elif company == "bonsae":
        @app.tool()
        def analyze_design(reference: str, target: str | None = None) -> dict[str, str]:
            """Inspect caller-provided HTML/CSS semantics, not rendered pixels."""
            return invoke(company, "analyze_design", {"reference": reference, "target": target})
        @app.tool()
        def generate_design_spec(brief: str) -> dict[str, str]:
            """Produce structured handoff from explicit components, states and tokens."""
            return invoke(company, "generate_design_spec", {"brief": brief})
        @app.tool()
        def review_visual(artifact: str) -> dict[str, str]:
            """Record design evidence gaps and hold visual PASS until pixels are inspected."""
            return invoke(company, "review_visual", {"artifact": artifact})

    elif company == "majung":
        @app.tool()
        def research_market(question: str, region: str | None = None) -> dict[str, str]:
            """Organize caller-supplied dated market evidence without web searches."""
            return invoke(company, "research_market", {"question": question, "region": region})
        @app.tool()
        def analyze_competitors(product: str) -> dict[str, str]:
            """Calculate competitor price positions from caller-supplied comparable prices."""
            return invoke(company, "analyze_competitors", {"product": product})
        @app.tool()
        def evaluate_opportunity(brief: str) -> dict[str, str]:
            """Compute unit economics; output only advisory HOLD/NO-GO, never authorize spend."""
            return invoke(company, "evaluate_opportunity", {"brief": brief})

    return app
