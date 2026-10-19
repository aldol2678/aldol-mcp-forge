from mcp_runtime import serve
from templates import get_tool
serve("aldol-game-html-audit", "0.1.0", [get_tool("html_audit")])
