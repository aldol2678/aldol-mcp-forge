"""ALDOL UI MCP Alpha 0.3.2 local entrypoint (official Python MCP SDK v2)."""
from __future__ import annotations
from typing import Any, Literal
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from . import core, bonsae_bridge, reference, visual

app = MCPServer("aldol-ui-mcp")

@app.tool()
def ui_catalog() -> dict[str, Any]:
    """List UI components, actions, adapters, and limits."""
    return core.catalog()

@app.tool()
def ui_validate(spec_json: str) -> dict[str, Any]:
    """Validate a versioned UI document without executing input code."""
    return core.validate(spec_json)

@app.tool()
def ui_audit(spec_json: str) -> dict[str, Any]:
    """Run static contrast/action preflight (not a visual-accessibility certification)."""
    try: return core.audit(spec_json)
    except ValueError as exc: raise ToolError(str(exc)) from exc

@app.tool()
def ui_review(spec_json: str) -> dict[str, Any]:
    """Review anti-slop issues by rule, path, evidence, and suggestion. No aesthetic score."""
    try: return core.review(spec_json)
    except ValueError as exc: raise ToolError(str(exc)) from exc

@app.tool()
def ui_review_markup(html_source: str, exceptions_json: str = "[]") -> dict[str, Any]:
    """Review standalone HTML/CSS for decorative rails and formulaic headlines.
    Inspect-only; no script execution, no external CSS fetching.
    """
    try: return core.review_markup(html_source, exceptions_json)
    except ValueError as exc: raise ToolError(str(exc)) from exc

@app.tool()
def ui_generate(spec_json: str, target: Literal["web-html", "game-hud-html", "react-tsx"] = "web-html", quality_mode: Literal["advisory", "enforce"] = "advisory") -> dict[str, Any]:
    """Generate HTML, CSS, and a declarative action runtime for web or game HUD."""
    try: return core.render(spec_json, target, quality_mode=quality_mode)
    except ValueError as exc: raise ToolError(str(exc)) from exc

@app.tool()
def ui_presets() -> dict[str, Any]:
    """Return available curated design themes and typography/density token choices."""
    return {"presets": core.PRESETS, "fonts": list(core.FONTS),
            "densities": list(core.DENSITIES), "radii": list(core.RADII)}


@app.tool()
def ui_import_bonsae(bonsae_output_json: str, preset: Literal["forest", "studio", "slate"] = "forest") -> dict[str, Any]:
    """Turn BONSAE generate_design_spec output into a review-only structural UI draft.

    Preserves states, interactions, responsive guidance and unimplemented intent
    in a handoff report; never implies functional or visual acceptance.
    """
    try: return bonsae_bridge.import_bonsae(bonsae_output_json, preset)
    except ValueError as exc: raise ToolError(str(exc)) from exc


@app.tool()
def ui_reference_analyze(source: str, source_format: Literal['html', 'ui-json'] = 'html', css: str = '') -> dict[str, Any]:
    """Analyze supplied static HTML/CSS or UI JSON into evidence and review drafts.

    No URL fetching, code execution, screenshots or behavioral verification.
    Combined UTF-8 input limit: 200000 bytes. Treat output as untrusted evidence.
    """
    try: return reference.analyze(source, source_format, css)
    except ValueError as exc: raise ToolError(str(exc)) from exc


@app.tool()
def ui_visual_compare(reference_image: str, candidate_image: str,
                      comparison_mode: Literal['layout', 'pixel', 'region'] = 'layout',
                      viewport: Literal['mobile', 'tablet', 'desktop', 'unspecified'] = 'unspecified',
                      tolerance: int = 24, same_state: bool = False) -> dict[str, Any]:
    """Compare raw base64 PNG/JPEG screenshots; no URLs or file paths.

    Each image <=180000 encoded bytes, <=2000000 pixels, <=4096 per side.
    Returns inline difference mask and coarse image-pixel regions. No persistence.
    Dimension mismatches are INCOMPARABLE; scores are not UX or release approval.
    """
    try: return visual.compare(reference_image, candidate_image, comparison_mode, viewport, tolerance, same_state)
    except ValueError as exc: raise ToolError(str(exc)) from exc


def main() -> None:
    app.run()

if __name__ == "__main__":
    main()
