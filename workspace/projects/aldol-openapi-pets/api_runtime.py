"""Runtime for v0.3-generated read-only OpenAPI MCP tools.

Dry-run is the default. Network must be deliberately enabled via environment.
No redirects, auth propagation, HTTP transport, or arbitrary host from a schema.
This does NOT protect from DNS rebinding; do not point at untrusted hosts.
"""
import ipaddress
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request

MAX_BODY = 262144


def _public_host(host):
    # Fail closed on DNS lookup failures and non-public addresses, including localhost.
    try:
        ips = [result[4][0] for result in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)]
        return bool(ips) and all(ipaddress.ip_address(ip).is_global for ip in ips)
    except (OSError, ValueError):
        return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirect blocked')


def call_operation(operation, arguments):
    """Dispatch approved GET operation; no network unless expressly enabled."""
    if operation['method'] != 'GET':
        raise ValueError('Only GET requests are supported')
    allowed = {p['name']: p for p in operation['parameters']}
    if arguments.keys() - allowed.keys():
        raise ValueError('Unexpected argument')
    path = operation['path']
    query = {}
    for p in operation['parameters']:
        name = p['name']
        value = arguments.get(name)
        if value is None:
            if p['required']:
                raise ValueError(f'Missing required parameter: {name}')
            continue
        kind = p['type']
        if kind == 'integer' and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError(f'{name} must be an integer')
        if kind == 'boolean' and not isinstance(value, bool):
            raise ValueError(f'{name} must be a boolean')
        if kind == 'string' and (not isinstance(value, str) or len(value) > 512):
            raise ValueError(f'{name} must be a string up to 512 characters')
        value = str(value).lower() if isinstance(value, bool) else str(value)
        if p['in'] == 'path':
            path = path.replace('{' + name + '}', urllib.parse.quote(value, safe=''))
        else:
            query[name] = value
    base = os.environ.get('ALDOL_API_BASE_URL', '').strip()
    if not base:
        return {'mode': 'dry_run', 'operation': operation['name'], 'method': 'GET',
                'path': path, 'query': query, 'network_called': False}
    u = urllib.parse.urlsplit(base)
    allowed_host = os.environ.get('ALDOL_API_ALLOWED_HOST', '').strip().lower()
    if (u.scheme != 'https' or not u.hostname or not allowed_host
            or u.hostname.lower() != allowed_host or u.username or u.password
            or u.port not in (None, 443) or u.query or u.fragment
            or not _public_host(u.hostname)):
        raise ValueError('Remote API needs HTTPS public host and matching ALDOL_API_ALLOWED_HOST')
    # Strip trailing slash but keep the explicitly configured base prefix.
    prefix = u.path.rstrip('/')
    url = urllib.parse.urlunsplit(('https', u.netloc, prefix + path,
                                urllib.parse.urlencode(query), ''))
    opener = urllib.request.build_opener(_NoRedirect())
    req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'ALDOL-MCP-Forge/0.3'}, method='GET')
    try:
        with opener.open(req, timeout=5) as response:
            if response.status != 200:
                raise ValueError(f'Unexpected HTTP status {response.status}')
            if 'application/json' not in response.headers.get('Content-Type', '').lower():
                raise ValueError('Only JSON API responses are supported')
            data = response.read(MAX_BODY + 1)
            if len(data) > MAX_BODY:
                raise ValueError('API response exceeds limit')
            return {'mode': 'live', 'operation': operation['name'], 'status': response.status,
                    'data': json.loads(data)}
    except urllib.error.HTTPError as exc:
        raise ValueError(f'API status {exc.code}') from exc
