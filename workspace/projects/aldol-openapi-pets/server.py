"""Generated from OpenAPI GET operations by ALDOL MCP Forge v0.3."""
import sys
from typing import Any
from api_runtime import call_operation
from operations import OPERATIONS

if __name__ == "__main__" and "--compat-smoke-test" in sys.argv:
    from mcp_runtime import Tool, serve
    tools = []
    for operation in OPERATIONS:
        schema = operation["schema"]
        tools.append(Tool(operation["name"], operation["description"], schema,
                          lambda args, op=operation: call_operation(op, args)))
    serve('aldol-openapi-pets', '0.3.0', tools)
else:
    from mcp.server import MCPServer
    app = MCPServer('aldol-openapi-pets')

    @app.tool()
    def list_pets(limit: int | None = None, active: bool | None = None) -> dict[str, Any]:
        'Read list of sample pets'
        return call_operation(OPERATIONS[0], {'limit': limit, 'active': active})

    @app.tool()
    def get_pet(pet_id: str) -> dict[str, Any]:
        'Read one sample pet'
        return call_operation(OPERATIONS[1], {'pet_id': pet_id})

    if __name__ == "__main__":
        app.run()
