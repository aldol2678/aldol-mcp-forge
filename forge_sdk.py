"""ALDOL MCP Forge official Python MCP SDK v2 stdio entrypoint.

Candidate v0.4 integration. The legacy stdio entrypoint in forge.py remains
available for compatibility; neither API writes nor deployments are automatic.

Run (after installing mcp>=2,<3):
    python forge_sdk.py
"""
import os
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

import forge


def _configure_workspace() -> None:
    """Allow an explicit isolated workspace for CI or local use.

    The configured directory must already exist. This is not a security
    sandbox: use only a workspace you trust, with appropriate OS permissions.
    """
    configured = os.environ.get("ALDOL_FORGE_WORKSPACE_ROOT")
    if not configured:
        return
    root = Path(configured).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("ALDOL_FORGE_WORKSPACE_ROOT must be an existing directory")
    forge.SPACE = root
    forge.PROJECTS = root / "projects"
    forge.PACKAGES = root / "packages"
    forge.HISTORY = root / "history"


_configure_workspace()
app = MCPServer("aldol-mcp-forge")


@app.tool()
def forge_list_templates() -> dict[str, Any]:
    """List the supported curated, read-only MCP tool templates."""
    return forge.TEMPLATE_INFO


@app.tool()
def forge_preview(description: str) -> dict[str, Any]:
    """Preview a natural language request; this operation creates no files."""
    return forge._preview({"description": description})


@app.tool()
def forge_create(project_name: str, description: str) -> dict[str, Any]:
    """Create a local MCP source project; never deploy or overwrite existing projects."""
    return forge._create({"project_name": project_name, "description": description})


@app.tool()
def forge_add_tool(
    project_name: str, description: str, isolation: str = "auto"
) -> dict[str, Any]:
    """Add a curated tool to a local project, retaining a versioned backup."""
    return forge._add_tool({"project_name": project_name, "description": description,
                            "isolation": isolation})


@app.tool()
def forge_test(project_name: str, isolation: str = "auto") -> dict[str, Any]:
    """Validate local project files and run its compatibility / SDK tests."""
    return forge._test({"project_name": project_name, "isolation": isolation})


@app.tool()
def forge_package(project_name: str, isolation: str = "auto") -> dict[str, Any]:
    """Create a local ZIP after testing; never upload or deploy the package."""
    return forge._package({"project_name": project_name, "isolation": isolation})


@app.tool()
def forge_preview_openapi(spec_json: str) -> dict[str, Any]:
    """Preview supported OpenAPI 3.x JSON GET methods without network calls."""
    return forge._preview_openapi({"spec_json": spec_json})


@app.tool()
def forge_import_openapi(
    project_name: str, spec_json: str, isolation: str = "auto"
) -> dict[str, Any]:
    """Create a local dry-run OpenAPI GET MCP project without live API calls."""
    return forge._import_openapi({"project_name": project_name, "spec_json": spec_json,
                                  "isolation": isolation})


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()
