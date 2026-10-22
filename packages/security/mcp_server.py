"""Official MCP SDK v2 stdio entrypoint. No remote transport is exposed."""
from typing import Any
from mcp.server import MCPServer
from engine import capabilities, scan, scan_all

app = MCPServer("aldol-security")


@app.tool()
def security_capabilities() -> dict[str, Any]:
    """Check scanner installation, database/OSV policy, and workspace readiness."""
    return capabilities()


@app.tool()
def security_scan_trivy(subpath: str = ".") -> dict[str, Any]:
    """Read-only local workspace vulnerability/config/secret scan. Secrets redacted."""
    return scan("trivy", subpath)


@app.tool()
def security_scan_osv(subpath: str = ".") -> dict[str, Any]:
    """Check dependencies via OSV. Requires explicit opt-in to external lookup."""
    return scan("osv", subpath)


@app.tool()
def security_inventory_sbom(subpath: str = ".") -> dict[str, Any]:
    """Generate read-only Syft CycloneDX inventory summary, not raw SBOM."""
    return scan("syft", subpath)


@app.tool()
def security_scan_all(subpath: str = ".") -> dict[str, Any]:
    """Run three scoped scanners and preserve UNKNOWN/BLOCKED gaps."""
    return scan_all(subpath)


if __name__ == "__main__":
    app.run()
