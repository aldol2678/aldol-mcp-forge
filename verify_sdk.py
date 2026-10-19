"""Verify a generated Forge server using the REAL official Python MCP SDK v2.

This script never substitutes a fake SDK or the Forge compatibility transport.
Two transports are exercised: Client(app) (in memory) and
Client(stdio_client(StdioServerParameters(...))) (a real child process over stdio).
Requires `mcp>=2,<3`; exit code 2 means dependency unavailable/wrong major version.
"""
import argparse
import asyncio
import importlib.metadata
import importlib.util
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

SAMPLE = {
    'html_audit': '<html lang="ko"><head><title>Test</title><meta name="viewport" content="width=device-width"></head><body></body></html>',
    'json_audit': '{"ok":true}',
    'text_stats': 'hello Forge',
}
API_VARS = ('ALDOL_API_BASE_URL', 'ALDOL_API_ALLOWED_HOST')


@contextmanager
def force_dry_run():
    old = {k: os.environ.get(k) for k in API_VARS}
    try:
        for k in API_VARS:
            os.environ.pop(k, None)
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def expected_tools(manifest):
    if manifest.get('kind') == 'openapi-get':
        ops = manifest['operations']
        if not ops or any(op['method'] != 'GET' for op in ops):
            raise ValueError('Only read-only OpenAPI GET operations can be verified')
        expected = [op['name'] for op in ops]
        arguments = {op['name']: {
            p['name']: {'string': 'sample', 'integer': 2, 'boolean': True}[p['type']]
            for p in op['parameters'] if p['required']
        } for op in ops}
    else:
        expected = manifest['templates']
        arguments = {name: {'content': SAMPLE[name]} for name in expected}
    return expected, arguments


async def run_calls(client, expected, arguments, is_openapi):
    observed = [tool.name for tool in (await client.list_tools()).tools]
    if len(observed) != len(expected) or set(observed) != set(expected):
        raise AssertionError(f'MCP tools mismatch: {observed} != {expected}')
    sample_results = {}
    for name in expected:
        response = await client.call_tool(name, arguments[name])
        if response.is_error or not response.content:
            raise AssertionError(f'Official MCP tool call failed: {name}')
        payload = response.structured_content
        if not isinstance(payload, dict):
            raise AssertionError(f'Missing SDK v2 structured_content: {name}')
        if 'result' in payload and isinstance(payload['result'], dict):
            payload = payload['result']
        if is_openapi and not (payload.get('mode') == 'dry_run'
                               and payload.get('network_called') is False
                               and payload.get('method') == 'GET'):
            raise AssertionError(f'Unexpected API network activity or result: {name}')
        sample_results[name] = payload
    return {'tools': observed, 'sample_results': sample_results,
            'protocol_version': str(client.protocol_version)}


async def verify(project, mode='both'):
    from mcp import Client, StdioServerParameters
    from mcp.client.stdio import stdio_client
    project = Path(project).resolve(strict=True)
    manifest = json.loads((project / 'manifest.json').read_text(encoding='utf-8'))
    if not (project / 'server.py').is_file():
        raise FileNotFoundError('Generated server.py is missing')
    expected, args = expected_tools(manifest)
    out = {}
    with force_dry_run():
        if mode in ('both', 'inmemory'):
            # Load untrusted code only from projects you created/reviewed.
            # This script is intended for trusted local generated projects.
            sys.path.insert(0, str(project))
            spec = importlib.util.spec_from_file_location('_forge_sdk_generated_server', project / 'server.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            async with Client(module.app, raise_exceptions=True) as client:
                out['inmemory'] = await run_calls(client, expected, args, manifest.get('kind') == 'openapi-get')
            sys.path.pop(0)
        if mode in ('both', 'stdio'):
            # An explicitly blank API target guarantees dry_run even if the parent
            # process has ALDOL_API_* variables set.
            params = StdioServerParameters(command=sys.executable,
                                           args=['-B', str(project / 'server.py')],
                                           env={'ALDOL_API_BASE_URL': '', 'ALDOL_API_ALLOWED_HOST': ''})
            async with Client(stdio_client(params), raise_exceptions=True) as client:
                out['stdio'] = await run_calls(client, expected, args, manifest.get('kind') == 'openapi-get')
    return {'passed': True, 'official_sdk': True,
            'validation': 'official Python MCP SDK v2',
            'sdk_version': importlib.metadata.version('mcp'),
            'transports': out, 'network_used': False}


def main():
    parser = argparse.ArgumentParser(description='Official MCP SDK v2 end-to-end verifier')
    parser.add_argument('project_dir')
    parser.add_argument('--mode', choices=['both', 'inmemory', 'stdio'], default='both')
    args = parser.parse_args()
    try:
        version = importlib.metadata.version('mcp')
    except importlib.metadata.PackageNotFoundError:
        print(json.dumps({'passed': False, 'status': 'unavailable',
                          'reason': 'Official Python MCP SDK is not installed',
                          'official_sdk_tested': False}))
        return 2
    if version.split('.')[0] != '2':
        print(json.dumps({'passed': False, 'status': 'unsupported_sdk',
                          'sdk_version': version, 'official_sdk_tested': False}))
        return 2
    try:
        result = asyncio.run(asyncio.wait_for(verify(args.project_dir, args.mode), timeout=40))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as e:
        print(json.dumps({'passed': False, 'status': 'failed', 'error': str(e),
                          'sdk_version': version, 'official_sdk_tested': True}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
