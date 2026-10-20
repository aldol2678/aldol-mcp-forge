"""Declarative, no-code-execution MCP scaffold compiler for Forge v0.4.

Contracts describe tool names, scalar inputs and object outputs. Generated
handlers fail closed until a developer deliberately implements and reviews them.
"""
import json
import keyword
import re

IDENT = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
KINDS = {"string": "str", "integer": "int", "number": "float", "boolean": "bool"}
RESERVED = {"app", "sys", "Any", "MCPServer", "ToolError", "Tool", "serve", "TOOLS", "not_implemented"}

def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result

def _identifier(value):
    return (isinstance(value, str) and IDENT.fullmatch(value)
            and not keyword.iskeyword(value) and value not in RESERVED)

def _schema_field(field, context):
    if not isinstance(field, dict) or set(field) - {"type", "description"}:
        raise ValueError(context + ": unsupported JSON Schema keywords")
    if field.get("type") not in KINDS:
        raise ValueError(context + ": only scalar types are supported")
    if "description" in field and (not isinstance(field["description"], str)
                                   or len(field["description"]) > 300):
        raise ValueError(context + ": invalid field description")
    return field

def parse_contract(raw):
    if not isinstance(raw, str) or not (2 <= len(raw) <= 120000):
        raise ValueError("contract_json must be 2..120000 characters")
    try:
        data = json.loads(raw, object_pairs_hook=_unique_pairs)
    except json.JSONDecodeError as exc:
        raise ValueError("contract_json must be valid JSON") from exc
    if not isinstance(data, dict) or set(data) != {"tools"}:
        raise ValueError("Contract requires only a tools array")
    rows = data["tools"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 12:
        raise ValueError("Contract requires 1..12 tools")
    seen = set()
    tools = []
    for tool in rows:
        if not isinstance(tool, dict) or set(tool) != {"name", "description", "inputs", "output_schema"}:
            raise ValueError("Tool requires name, description, inputs and output_schema")
        name, desc = tool["name"], tool["description"]
        if not _identifier(name) or name in seen:
            raise ValueError("Unsafe or duplicate tool name")
        seen.add(name)
        if not isinstance(desc, str) or not 1 <= len(desc.strip()) <= 500:
            raise ValueError("Tool description must be 1..500 characters")
        inputs = tool["inputs"]
        if not isinstance(inputs, list) or len(inputs) > 12:
            raise ValueError("Tool inputs must be an array of at most 12 fields")
        input_names = set()
        for field in inputs:
            if not isinstance(field, dict) or set(field) - {"name", "type", "required", "description"}:
                raise ValueError("Invalid input field keys")
            n = field.get("name")
            if not _identifier(n) or n in input_names:
                raise ValueError("Unsafe or duplicate input name")
            input_names.add(n)
            _schema_field({k: v for k, v in field.items() if k in ("type", "description")}, n)
            if type(field.get("required")) is not bool:
                raise ValueError("Input required must be boolean")
        out = tool["output_schema"]
        if (not isinstance(out, dict) or set(out) != {"type", "properties", "required", "additionalProperties"}
            or out["type"] != "object" or out["additionalProperties"] is not False):
            raise ValueError("Output must be a closed object JSON Schema")
        props = out["properties"]
        required = out["required"]
        if not isinstance(props, dict) or not 1 <= len(props) <= 20:
            raise ValueError("Output requires 1..20 scalar properties")
        if (not isinstance(required, list) or len(required) != len(set(required))
            or not all(isinstance(n, str) and n in props for n in required)):
            raise ValueError("Output required must list existing property names")
        for n, field in props.items():
            if not _identifier(n):
                raise ValueError("Unsafe output property name")
            _schema_field(field, n)
        tools.append(tool)
    return {"tools": tools}

def input_schema(tool):
    return {"type": "object",
            "properties": {f["name"]: {"type": f["type"],
                          **({"maxLength": 4096} if f["type"] == "string" else {}),
                          **({"description": f["description"]} if "description" in f else {})}
                           for f in tool["inputs"]},
            "required": [f["name"] for f in tool["inputs"] if f["required"]],
            "additionalProperties": False}

def render_server(name, tools):
    lines = [
        '"""Generated scaffold by ALDOL MCP Forge v0.4. No handlers are implemented."""',
        "import sys",
        "from typing import Any",
        "",
        "def not_implemented(tool_name: str) -> dict[str, Any]:",
        '    raise ValueError("NOT_IMPLEMENTED: " + tool_name)',
        "",
        'if __name__ == "__main__" and "--compat-smoke-test" in sys.argv:',
        "    from mcp_runtime import Tool, serve",
        "    tools = []",
    ]
    for tool in tools:
        lines.append("    tools.append(Tool(" + repr(tool["name"]) + ", " + repr(tool["description"]) +
                     ", " + repr(input_schema(tool)) + ", " +
                     "lambda args, n=" + repr(tool["name"]) + ": not_implemented(n)))")
    lines.extend([
        "    serve(" + repr(name) + ", '0.4.0', tools)",
        "else:",
        "    from mcp.server import MCPServer",
        "    from mcp.server.mcpserver.exceptions import ToolError",
        "    app = MCPServer(" + repr(name) + ")",
    ])
    for tool in tools:
        fields = sorted(tool["inputs"], key=lambda f: not f["required"])
        params = ", ".join(f["name"] + ": " + KINDS[f["type"]] +
                           ("" if f["required"] else " | None = None") for f in fields)
        lines.extend([
            "",
            "    @app.tool()",
            "    def " + tool["name"] + "(" + params + ") -> dict[str, Any]:",
            "        " + repr(tool["description"]),
            "        raise ToolError(" + repr("NOT_IMPLEMENTED: " + tool["name"]) + ")",
        ])
    lines.extend(["", '    if __name__ == "__main__":', "        app.run()", ""])
    return "\n".join(lines)

def readme(name, tools):
    listing = "\n".join("- " + x["name"] + ": " + x["description"] for x in tools)
    return ("# " + name + "\n\nALDOL MCP Forge v0.4 declarative scaffold.\n\n" +
            "Tools:\n" + listing + "\n\n" +
            "Python 3.11+. Install mcp>=2,<3 then run python server.py.\n\n" +
            "IMPORTANT: every tool raises NOT_IMPLEMENTED. The saved contract.json\n" +
            "contains the proposed input/output shapes; the output schema is NOT\n" +
            "enforced by the SDK until a developer implements and tests handlers.\n" +
            "No API calls, filesystem edits, credentials, or deployment are generated.\n" +
            "The --compat-smoke-test mode is not an official SDK test.\n" +
            "Do not trust edited server.py until reviewed and tested independently.\n")
