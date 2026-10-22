"""ALDOL RIGHTS MCP v0.1 (Python MCP SDK v2). Run `python server.py` for stdio."""
from __future__ import annotations

from typing import Any

from core import (
    register_asset as _register_asset, inspect_license as _inspect_license,
    check_usage as _check_usage, generate_credits as _generate_credits,
    rights_report as _rights_report,
)

from mcp.server import MCPServer

app = MCPServer("aldol-rights")


@app.tool()
def register_asset(title: str, kind: str, license_id: str = "UNKNOWN", creator: str = "",
                   rights_holder: str = "", source_url: str = "", license_url: str = "",
                   evidence_url: str = "", notes: str = "") -> dict[str, Any]:
    """Record an asset and its *unverified* licensing evidence in a local SQLite DB."""
    return _register_asset(title, kind, license_id, creator, rights_holder, source_url, license_url, evidence_url, notes)


@app.tool()
def inspect_license(license_id: str) -> dict[str, Any]:
    """Show simplified CC 4.0 conditions; does not verify a specific asset's rights."""
    return _inspect_license(license_id)


@app.tool()
def check_usage(asset_id: str, commercial: bool = False, modified: bool = False,
                redistribute: bool = True, attribution_planned: bool = False,
                derivative_license: str = "") -> dict[str, Any]:
    """Preflight an asset's proposed use, blocking known NC/ND conflicts."""
    return _check_usage(asset_id, commercial, modified, redistribute, attribution_planned, derivative_license)


@app.tool()
def generate_credits(asset_ids_json: str = "[]", format: str = "markdown") -> dict[str, Any]:
    """Draft attribution lines, identifying missing evidence and author metadata."""
    return _generate_credits(asset_ids_json, format)


@app.tool()
def rights_report(asset_ids_json: str = "[]", commercial: bool = True,
                  modified: bool = False, redistribute: bool = True,
                  attribution_planned: bool = False, derivative_license: str = "") -> dict[str, Any]:
    """Audit up to 500 assets for a specific usage; never returns legal approval."""
    return _rights_report(asset_ids_json, commercial, modified, redistribute, attribution_planned, derivative_license)


if __name__ == "__main__":
    app.run()
