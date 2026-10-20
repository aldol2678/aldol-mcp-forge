"""ALDOL MCP Forge official Python MCP SDK v2 stdio entrypoint.

Candidate v0.4 integration. The legacy stdio entrypoint in forge.py remains
available for compatibility; neither API writes nor deployments are automatic.

Run (after installing mcp>=2,<3):
    python forge_sdk.py
"""
import os
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent

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
# The official SDK 2.0.0 decorator silently drops unknown keys from tool
# arguments. Legacy Forge rejected them; preserve that behavior at the
# pre-validation boundary. This middleware only REFUSES unknown arguments.
_ALLOWED_TOOL_KEYS: dict[str, frozenset[str]] = {
    "forge_list_templates": frozenset(),
    "forge_preview": frozenset({"description"}),
    "forge_create": frozenset({"project_name", "description"}),
    "forge_add_tool": frozenset({"project_name", "description", "isolation"}),
    "forge_test": frozenset({"project_name", "isolation"}),
    "forge_package": frozenset({"project_name", "isolation"}),
    "forge_preview_openapi": frozenset({"spec_json"}),
    "forge_import_openapi": frozenset({"project_name", "spec_json", "isolation"}),
    "forge_preview_contract": frozenset({"contract_json"}),
    "forge_create_contract": frozenset({"project_name", "contract_json", "isolation"}),
}


async def reject_unknown_tool_arguments(ctx, call_next):
    if ctx.method != "tools/call":
        return await call_next(ctx)
    params = ctx.params
    if isinstance(params, dict):
        name, arguments = params.get("name"), params.get("arguments", {})
    else:
        name = getattr(params, "name", None)
        arguments = getattr(params, "arguments", {})
    if name in _ALLOWED_TOOL_KEYS and isinstance(arguments, dict):
        unknown = arguments.keys() - _ALLOWED_TOOL_KEYS[name]
        if unknown:
            return CallToolResult(
                is_error=True,
                content=[TextContent(type="text", text="unknown argument(s): " +
                                     ", ".join(sorted(unknown)))],
            )
    return await call_next(ctx)


app = MCPServer("aldol-mcp-forge", middleware=[reject_unknown_tool_arguments])

# Match the legacy public argument contract, including bounds and enum values.
ProjectName = Annotated[str, Field(min_length=1, max_length=40)]
Description = Annotated[str, Field(min_length=1, max_length=2000)]
OpenAPISpec = Annotated[str, Field(min_length=2, max_length=120000)]
ContractSpec = Annotated[str, Field(min_length=2, max_length=120000)]
Isolation = Annotated[Literal["auto", "strict"], Field(min_length=1, max_length=40)]


def _expected_failure(operation, arguments: dict[str, Any]) -> dict[str, Any]:
    """Keep expected user errors visible to a calling MCP client.

    Unexpected exceptions deliberately escape so the SDK logs and sanitizes
    them instead of exposing host internals.
    """
    try:
        return operation(arguments)
    except (ValueError, RuntimeError, OSError) as exc:
        raise ToolError(str(exc)) from exc



@app.tool()
def forge_list_templates() -> dict[str, Any]:
    """List the supported curated, read-only MCP tool templates."""
    return forge.TEMPLATE_INFO


@app.tool()
def forge_preview(description: Description) -> dict[str, Any]:
    """Preview a natural language request; this operation creates no files."""
    return _expected_failure(forge._preview, {"description": description})


@app.tool()
def forge_create(project_name: ProjectName, description: Description) -> dict[str, Any]:
    """Create a local MCP source project; never deploy or overwrite existing projects."""
    return _expected_failure(forge._create, {"project_name": project_name, "description": description})


@app.tool()
def forge_add_tool(
    project_name: ProjectName, description: Description, isolation: Isolation = "auto"
) -> dict[str, Any]:
    """Add a curated tool to a local project, retaining a versioned backup."""
    return _expected_failure(forge._add_tool, {"project_name": project_name, "description": description,
                            "isolation": isolation})


@app.tool()
def forge_test(project_name: ProjectName, isolation: Isolation = "auto") -> dict[str, Any]:
    """Validate local project files and run its compatibility / SDK tests."""
    return _expected_failure(forge._test, {"project_name": project_name, "isolation": isolation})


@app.tool()
def forge_package(project_name: ProjectName, isolation: Isolation = "auto") -> dict[str, Any]:
    """Create a local ZIP after testing; never upload or deploy the package."""
    return _expected_failure(forge._package, {"project_name": project_name, "isolation": isolation})


@app.tool()
def forge_preview_openapi(spec_json: OpenAPISpec) -> dict[str, Any]:
    """Preview supported OpenAPI 3.x JSON GET methods without network calls."""
    return _expected_failure(forge._preview_openapi, {"spec_json": spec_json})


@app.tool()
def forge_import_openapi(
    project_name: ProjectName, spec_json: OpenAPISpec, isolation: Isolation = "auto"
) -> dict[str, Any]:
    """Create a local dry-run OpenAPI GET MCP project without live API calls."""
    return _expected_failure(forge._import_openapi, {"project_name": project_name, "spec_json": spec_json,
                                  "isolation": isolation})


@app.tool()
def forge_preview_contract(contract_json: ContractSpec) -> dict[str, Any]:
    """Validate a declarative tool contract without files or execution."""
    return _expected_failure(forge._preview_contract, {"contract_json": contract_json})


@app.tool()
def forge_create_contract(
    project_name: ProjectName, contract_json: ContractSpec, isolation: Isolation = "auto"
) -> dict[str, Any]:
    """Generate a fail-closed SDK tool scaffold, not implementation or deployment."""
    return _expected_failure(forge._create_contract,
                             {"project_name": project_name, "contract_json": contract_json,
                              "isolation": isolation})


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()
