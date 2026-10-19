"""Minimal, dependency-free MCP stdio JSON-RPC transport for Forge v0.1.

This is a limited implementation for tools-only servers, not a replacement for
full official MCP SDKs. Requests must be newline-delimited JSON objects.
"""
import json
import sys
from dataclasses import dataclass
from typing import Callable

PROTOCOL = '2026-07-28'
MAX_MESSAGE = 300_000


@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    handler: Callable
    read_only: bool = True

    def descriptor(self):
        return {
            'name': self.name,
            'description': self.description,
            'inputSchema': self.schema,
            'annotations': {
                'readOnlyHint': self.read_only,
                'destructiveHint': False,
                'openWorldHint': False,
            },
        }


def _validate(schema, arguments):
    if not isinstance(arguments, dict):
        raise ValueError('arguments must be an object')
    properties = schema.get('properties', {})
    if schema.get('additionalProperties') is False:
        unknown = arguments.keys() - properties.keys()
        if unknown:
            raise ValueError('unknown argument(s): ' + ', '.join(sorted(unknown)))
    for name in schema.get('required', []):
        if name not in arguments:
            raise ValueError(f'missing required argument: {name}')
    for name, value in arguments.items():
        spec = properties.get(name, {})
        expected = spec.get('type')
        if expected == 'string' and not isinstance(value, str):
            raise ValueError(f'{name} must be string')
        if expected == 'integer' and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError(f'{name} must be integer')
        if isinstance(value, str) and len(value) > spec.get('maxLength', 999_999):
            raise ValueError(f'{name} too long')
        if isinstance(value, str) and len(value) < spec.get('minLength', 0):
            raise ValueError(f'{name} too short')


def serve(name: str, version: str, tools: list[Tool]):
    registry = {tool.name: tool for tool in tools}
    initialized = False
    for raw in sys.stdin.buffer:
        request_id = None
        try:
            if len(raw) > MAX_MESSAGE:
                raise ValueError('message too large')
            msg = json.loads(raw)
            if not isinstance(msg, dict) or msg.get('jsonrpc') != '2.0':
                raise ValueError('invalid JSON-RPC request')
            method = msg.get('method')
            request_id = msg.get('id')
            if method is None:
                continue
            if method == 'initialize':
                params = msg.get('params') or {}
                if not isinstance(params, dict):
                    raise ValueError('invalid initialize params')
                result = {
                    'protocolVersion': PROTOCOL,
                    'capabilities': {'tools': {'listChanged': False}},
                    'serverInfo': {'name': name, 'version': version},
                }
                initialized = True
            elif method == 'notifications/initialized':
                continue
            elif not initialized:
                raise ValueError('server is not initialized')
            elif method == 'ping':
                result = {}
            elif method == 'tools/list':
                result = {'tools': [t.descriptor() for t in tools]}
            elif method == 'tools/call':
                params = msg.get('params') or {}
                if not isinstance(params, dict):
                    raise ValueError('invalid call params')
                tool_name = params.get('name')
                if tool_name not in registry:
                    raise ValueError('unknown tool')
                tool = registry[tool_name]
                try:
                    args = params.get('arguments', {})
                    _validate(tool.schema, args)
                    output = tool.handler(args)
                    result = {'content': [{'type': 'text', 'text': json.dumps(output, ensure_ascii=False)}]}
                except (ValueError, RuntimeError, OSError) as e:
                    result = {'isError': True, 'content': [{'type': 'text', 'text': str(e)}]}
            else:
                if request_id is not None:
                    sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': request_id, 'error': {'code': -32601, 'message': 'Method not found'}}, ensure_ascii=False) + '\n')
                    sys.stdout.flush()
                continue
            if request_id is not None:
                sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': request_id, 'result': result}, ensure_ascii=False) + '\n')
                sys.stdout.flush()
        except (ValueError, json.JSONDecodeError) as e:
            if request_id is not None:
                sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': request_id, 'error': {'code': -32602, 'message': str(e)}}, ensure_ascii=False) + '\n')
                sys.stdout.flush()


def str_schema(*required):
    props = {key: {'type': 'string', 'minLength': 1, 'maxLength': 220_000} for key in required}
    return {'type': 'object', 'properties': props, 'required': list(required), 'additionalProperties': False}
