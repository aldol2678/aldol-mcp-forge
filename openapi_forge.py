"""Conservative OpenAPI 3 JSON -> read-only MCP SDK v2 project compiler.

No source code from the OpenAPI spec is evaluated. Accepts a narrow subset and
rejects rather than silently drops unsupported GET parameters.
"""
import hashlib
import json
import keyword
import re
from pathlib import Path

from api_runtime import call_operation

PARAM_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
OP_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')
PATH_RE = re.compile(r'^/(?:[A-Za-z0-9_.~-]|\{[A-Za-z_][A-Za-z0-9_]*\}|/|-|%[a-fA-F0-9]{2})+$')


def parse_openapi(spec_text):
    if not isinstance(spec_text, str) or len(spec_text) > 120000:
        raise ValueError('OpenAPI JSON text must be at most 120000 characters')
    try:
        doc = json.loads(spec_text)
    except json.JSONDecodeError as exc:
        raise ValueError('OpenAPI specification must be JSON') from exc
    if not isinstance(doc, dict) or not re.match(r'^3\.(0|1)\.[0-9]+$', str(doc.get('openapi', ''))):
        raise ValueError('Only OpenAPI 3.0.x or 3.1.x is supported')
    if not isinstance(doc.get('info', {}), dict):
        raise ValueError('OpenAPI info must be an object')
    paths = doc.get('paths')
    if not isinstance(paths, dict) or len(paths) > 64:
        raise ValueError('paths must be an object with <=64 entries')
    operations = []
    used = set()
    skipped = []
    for path, item in paths.items():
        if (not isinstance(path, str) or not PATH_RE.fullmatch(path) or path.startswith('//')
                or '%' in path or any(segment in ('.', '..') for segment in path.split('/'))):
            raise ValueError('Unsupported or unsafe API path')
        if not isinstance(item, dict) or '$ref' in item:
            raise ValueError('Path must be an inline object')
        for method in ['post', 'put', 'patch', 'delete', 'trace', 'head', 'options']:
            if method in item:
                skipped.append({'method': method.upper(), 'path': path, 'reason': 'non-GET excluded'})
        if 'get' not in item:
            continue
        op = item['get']
        if not isinstance(op, dict) or '$ref' in op:
            raise ValueError('GET operation must be inline')
        name = op.get('operationId')
        if (not isinstance(name, str) or not OP_RE.fullmatch(name) or keyword.iskeyword(name)
                or name.startswith('_') or len(name) > 64 or name in used
                or name in {'app', 'sys', 'MCPServer', 'OPERATIONS', 'call_operation', 'Tool', 'serve'}):
            raise ValueError('GET operationId must be unique safe Python identifier')
        used.add(name)
        if not isinstance(item.get('parameters', []), list) or not isinstance(op.get('parameters', []), list):
            raise ValueError('Unsupported GET parameters')
        raw_params = item.get('parameters', []) + op.get('parameters', [])
        if len(raw_params) > 12:
            raise ValueError('Unsupported GET parameters')
        parameters = []
        seen = set()
        for p in raw_params:
            if not isinstance(p, dict) or '$ref' in p or p.get('in') not in ('path', 'query'):
                raise ValueError('Only inline path and query parameters are supported')
            pn = p.get('name')
            if not isinstance(pn, str) or not PARAM_RE.fullmatch(pn) or keyword.iskeyword(pn) or pn in seen:
                raise ValueError('Parameter name is unsafe or duplicated')
            seen.add(pn)
            schema = p.get('schema', {})
            if not isinstance(schema, dict) or schema.get('type') not in ('string', 'integer', 'boolean') or '$ref' in schema:
                raise ValueError('Only inline string/integer/boolean parameter schemas supported')
            if any(key in p for key in ('content', 'style', 'explode', 'allowReserved')):
                raise ValueError('Advanced parameter encoding not supported')
            required = p.get('in') == 'path' or p.get('required') is True
            if p.get('in') == 'path' and p.get('required') is not True:
                raise ValueError('Path parameters must explicitly be required')
            parameters.append({'name': pn, 'in': p['in'], 'required': required, 'type': schema['type']})
        path_names = set(re.findall(r'\{(\w+)\}', path))
        if path_names != {p['name'] for p in parameters if p['in'] == 'path'}:
            raise ValueError('All URL path placeholders must have matching path parameters')
        description = str(op.get('summary') or op.get('description') or 'Read-only API GET operation')[:180]
        operations.append({'name': name, 'method': 'GET', 'path': path, 'description': description, 'parameters': parameters})
        if len(operations) > 12:
            raise ValueError('Maximum 12 GET operations per imported project')
    if not operations:
        raise ValueError('No supported GET operations in specification')
    return {'operations': operations, 'skipped': skipped, 'title': str(doc.get('info', {}).get('title', 'API'))[:100]}


def _schema(op):
    return {'type': 'object', 'properties': {
        p['name']: {'type': p['type'], **({'maxLength': 512} if p['type'] == 'string' else {})}
        for p in op['parameters']},
        'required': [p['name'] for p in op['parameters'] if p['required']], 'additionalProperties': False}


def render_server(name, version, operations):
    # All injected identifiers have passed strict allowlist validation.
    lines = [
        '"""Generated from OpenAPI GET operations by ALDOL MCP Forge v0.3."""',
        'import sys', 'from api_runtime import call_operation',
        'from operations import OPERATIONS', '',
        'if __name__ == "__main__" and "--compat-smoke-test" in sys.argv:',
        '    from mcp_runtime import Tool, serve',
        '    tools = []',
        '    for operation in OPERATIONS:',
        '        schema = operation["schema"]',
        '        tools.append(Tool(operation["name"], operation["description"], schema,',
        '                          lambda args, op=operation: call_operation(op, args)))',
        f'    serve({name!r}, {version!r}, tools)',
        'else:',
        '    from mcp.server import MCPServer',
        f'    app = MCPServer({name!r})',
    ]
    for i, op in enumerate(operations):
        params = [p for p in op['parameters'] if p['required']] + [p for p in op['parameters'] if not p['required']]
        pytype = {'string': 'str', 'integer': 'int', 'boolean': 'bool'}
        signature = ', '.join(p['name'] + ': ' + pytype[p['type']] + ('' if p['required'] else ' | None = None') for p in params)
        vals = ', '.join(repr(p['name']) + ': ' + p['name'] for p in params)
        lines += ['', '    @app.tool()', f'    def {op["name"]}({signature}) -> dict:',
                  f'        {op["description"]!r}',
                  f'        return call_operation(OPERATIONS[{i}], {{{vals}}})']
    lines += ['', '    if __name__ == "__main__":', '        app.run()', '']
    return '\n'.join(lines)


def render_operations(operations):
    data = [{**op, 'schema': _schema(op)} for op in operations]
    return '"""Generated operation registry. Treat external specs as untrusted input."""\nOPERATIONS = ' + repr(data) + '\n'


def readme(name, parsed):
    return f'''# {name} (OpenAPI GET MCP)

Generated by ALDOL MCP Forge v0.3 from OpenAPI v3 JSON.

- Exposed read-only GET operations: {', '.join(x['name'] for x in parsed['operations'])}
- Skipped non-GET operations: {len(parsed['skipped'])}
- Python 3.11+. `pip install -r requirements.txt && python server.py`

## Safe defaults

Without `ALDOL_API_BASE_URL`, tools **only return a dry-run request preview**. No network access.
To explicitly enable real requests configure both `ALDOL_API_BASE_URL=https://public.example.com/v1`
and `ALDOL_API_ALLOWED_HOST=public.example.com` in the server process environment.
Only public HTTPS hosts on port 443, GET, JSON responses up to 256KiB, 5s timeouts and no HTTP redirects are supported.
API keys, OAuth, request bodies, references, complex parameter serialization, and WebSockets are unsupported.

**Security limitations:** DNS rebinding is not comprehensively eliminated; use only trusted public API hosts,
review the endpoint path and operations before enabling network access. Test execution has limited isolation,
not a fully confined sandbox. Official SDK execution requires installing mcp 2.x separately.

## Offline check

`python server.py --compat-smoke-test` uses a small compatibility transport, NOT the official SDK.
Use the forge `forge_test` tool, and run `verify_sdk.py` from Forge when SDK v2 is available.
'''


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
