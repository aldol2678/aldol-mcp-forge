"""Official SDK v2 over real HTTP plus private-specialist isolation regression.

Temporary random bearer credentials exist only in process memory and child env.
No credentials, logs containing credentials, or caller artifacts are persisted.
"""
from __future__ import annotations
import asyncio
import hashlib
import http.client
import importlib.metadata
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import unittest

from enterprise_mcps.specialist_http import MAX_BODY, create_http_app
from enterprise_mcps.tests.test_sdk import verify_client

ROOT = Path(__file__).resolve().parents[2]


class PrivateSpecialistHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.processes = []
        cls.servers = {}
        try:
            for company in ('bonsae', 'majung'):
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 0))
                    port = sock.getsockname()[1]
                token = secrets.token_urlsafe(48)
                env = {**os.environ, 'ALDOL_COMPANY': company,
                       'ALDOL_MCP_BEARER_TOKEN': token, 'PORT': str(port),
                       'PYTHONPATH': str(ROOT), 'PYTHONDONTWRITEBYTECODE': '1'}
                # Local tests may run in an operator shell that has Railway vars.
                for name in ('RAILWAY_PUBLIC_DOMAIN', 'ALDOL_PUBLIC_HOST'):
                    env.pop(name, None)
                process = subprocess.Popen([sys.executable, '-B', '-m', 'enterprise_mcps.specialist_http'],
                    cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                cls.processes.append(process)
                cls.servers[company] = {'port': port, 'token': token}
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise AssertionError('Private HTTP process failed to start')
                    try:
                        status, _, body = cls.request(company, 'GET', '/healthz')
                        if status == 200 and json.loads(body)['company'] == company:
                            break
                    except (OSError, ValueError):
                        pass
                    time.sleep(.05)
                else:
                    raise AssertionError('Private HTTP health endpoint did not become ready')
        except BaseException:
            cls._stop_processes()
            raise

    @classmethod
    def _stop_processes(cls):
        for process in cls.processes:
            process.terminate()
        for process in cls.processes:
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
            for server in cls.servers.values():
                if server['token'] in stdout or server['token'] in stderr:
                    raise AssertionError('Server process log exposed bearer credential')

    @classmethod
    def tearDownClass(cls):
        cls._stop_processes()

    @classmethod
    def request(cls, company, method, path, body=None, auth=None, duplicate=False, extra_headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', cls.servers[company]['port'], timeout=5)
        try:
            connection.putrequest(method, path)
            connection.putheader('Content-Type', 'application/json')
            if auth is not None:
                connection.putheader('Authorization', 'Bearer ' + auth)
                if duplicate:
                    connection.putheader('Authorization', 'Bearer ' + auth)
            for key, value in (extra_headers or {}).items():
                connection.putheader(key, value)
            if body is not None:
                if isinstance(body, str):
                    body = body.encode()
                connection.putheader('Content-Length', str(len(body)))
            connection.endheaders(body)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode()
        finally:
            connection.close()

    def assert_no_secrets(self, value):
        serialized = json.dumps(value)
        for server in self.servers.values():
            if server['token'] in serialized:
                raise AssertionError('HTTP/SDK response exposed a bearer credential')

    def test_01_public_health_is_minimal_and_status_requires_auth(self):
        for company in self.servers:
            with self.subTest(company=company):
                status, _, body = self.request(company, 'GET', '/healthz')
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body), {'healthy': True, 'company': company})
                status, headers, body = self.request(company, 'GET', '/status')
                self.assertEqual(status, 401)
                self.assertEqual(headers.get('cache-control'), 'no-store')
                self.assert_no_secrets(body)
                status, _, body = self.request(company, 'GET', '/status', auth=self.servers[company]['token'])
                self.assertEqual(status, 200)
                payload = json.loads(body)
                self.assertEqual(payload['company'], company)
                self.assertTrue(payload['authenticated'])
                self.assertEqual(payload['sdk'], '2.0.0')
                self.assert_no_secrets(payload)

    def test_02_no_auth_duplicate_auth_and_cross_company_tokens_rejected(self):
        body = '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
        for company, other in [('bonsae', 'majung'), ('majung', 'bonsae')]:
            for auth, duplicate in [(None, False), (self.servers[company]['token'], True),
                                    (self.servers[other]['token'], False)]:
                with self.subTest(company=company, duplicate=duplicate, auth_present=auth is not None):
                    status, _, response = self.request(company, 'POST', '/mcp', body,
                                                       auth=auth, duplicate=duplicate)
                    self.assertEqual(status, 401)
                    self.assert_no_secrets(response)

    def test_03_body_limit_and_route_method_restrictions(self):
        token = self.servers['bonsae']['token']
        status, _, body = self.request('bonsae', 'POST', '/mcp', b'x' * (MAX_BODY + 1), auth=token)
        self.assertEqual(status, 413)
        self.assertEqual(json.loads(body)['error'], 'request_too_large')
        self.assert_no_secrets(body)
        self.assertEqual(self.request('bonsae', 'GET', '/mcp', auth=token)[0], 405)
        self.assertEqual(self.request('bonsae', 'POST', '/seum/mcp', '{}', auth=token)[0], 404)

    def test_04_factory_rejects_unknown_company_and_invalid_secrets(self):
        for company in ['seum', 'unknown', 'bonsae;majung']:
            with self.subTest(company=company), self.assertRaisesRegex(RuntimeError, 'select bonsae or majung'):
                create_http_app(company=company, secret=self.servers['bonsae']['token'])
        for secret in ['', 'short', 'a' * 39, 'a' * 257, 'a' * 40 + '\n', '가' * 40]:
            with self.subTest(length=len(secret)), self.assertRaisesRegex(RuntimeError, 'bearer secret'):
                create_http_app(company='bonsae', secret=secret)

    def test_05_official_sdk_v2_real_http_discovers_and_calls_six_tools(self):
        self.assertEqual(importlib.metadata.version('mcp'), '2.0.0')
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client
        import httpx2
        async def run():
            receipts = []
            for company, settings in self.servers.items():
                async with httpx2.AsyncClient(headers={'Authorization': 'Bearer ' + settings['token']}, timeout=10, trust_env=False) as http:
                    url = f"http://127.0.0.1:{settings['port']}/mcp"
                    async with Client(streamable_http_client(url, http_client=http, terminate_on_close=False),
                                      raise_exceptions=True, cache=None) as client:
                        receipts.append(await verify_client(client, company))
            return receipts
        reports = asyncio.run(asyncio.wait_for(run(), timeout=40))
        self.assertEqual(sum(item['called'] for item in reports), 6)
        self.assertEqual({item['company'] for item in reports}, {'bonsae', 'majung'})
        self.assert_no_secrets(reports)

    def test_06_sdk_unknown_tool_and_invalid_input_are_denied(self):
        from mcp import Client
        from mcp.client.streamable_http import streamable_http_client
        from mcp.shared.exceptions import MCPError
        import httpx2
        async def run():
            settings = self.servers['bonsae']
            async with httpx2.AsyncClient(headers={'Authorization': 'Bearer ' + settings['token']}, timeout=10, trust_env=False) as http:
                async with Client(streamable_http_client(f"http://127.0.0.1:{settings['port']}/mcp",
                    http_client=http, terminate_on_close=False), cache=None) as client:
                    for name, args in [('evaluate_opportunity', {'brief': '{}'}), ('analyze_design', {'reference': 123})]:
                        try:
                            result = await client.call_tool(name, args)
                        except MCPError as exc:
                            # Transport errors must fail this test; only actual protocol errors count.
                            self.assert_no_secrets(str(exc))
                        else:
                            self.assertTrue(result.is_error)
                            self.assert_no_secrets(result.model_dump())
        asyncio.run(asyncio.wait_for(run(), timeout=25))

    def test_07_seum_implementation_and_three_tool_contract_are_unchanged(self):
        # Canonical PR #13 SEUM implementation is byte-for-byte retained.
        expected = '8653bcad17f6d62e9c56f600b386b0650adde92e2d95f5e05fe0ffc151697267'
        self.assertEqual(hashlib.sha256((ROOT / 'enterprise_mcps/seum.py').read_bytes()).hexdigest(), expected)
        from mcp import Client
        from enterprise_mcps.server import create_app
        async def run():
            async with Client(create_app('seum'), raise_exceptions=True, cache=None) as client:
                return await verify_client(client, 'seum')
        result = asyncio.run(asyncio.wait_for(run(), timeout=15))
        self.assertEqual(result['called'], 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
