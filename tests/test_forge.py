"""Offline regression suite for Forge v0.2.

SDK v2 interoperability is intentionally not claimed by these tests.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import forge
from sandbox import namespace_ready, run_server
from templates import html_audit, json_audit, select_template


class ForgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = forge.PROJECTS, forge.PACKAGES, forge.HISTORY
        forge.PROJECTS = Path(self.tmp.name) / 'projects'
        forge.PACKAGES = Path(self.tmp.name) / 'packages'
        forge.HISTORY = Path(self.tmp.name) / 'history'

    def tearDown(self):
        forge.PROJECTS, forge.PACKAGES, forge.HISTORY = self.old
        self.tmp.cleanup()

    def create(self, name='sample-html', desc='HTML 게임 검사'):
        return forge._create({'project_name': name, 'description': desc})

    def test_template_resolution(self):
        self.assertEqual(select_template('HTML 게임 검사'), 'html_audit')
        self.assertEqual(select_template('JSON 검사'), 'json_audit')
        self.assertEqual(select_template('문장 단어 수'), 'text_stats')
        self.assertIsNone(select_template('이메일 발송'))

    def test_path_traversal(self):
        for slug in ('../outside', 'bad_name', 'c', '/tmp/name', 'UPPER', 'a' * 41):
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                self.create(slug)

    def test_unsupported_request_and_dup_project(self):
        with self.assertRaises(ValueError):
            self.create('unsupported', '송금 자동화')
        self.create()
        with self.assertRaises(ValueError):
            self.create()

    def test_all_templates_generate_smoke_package(self):
        for slug, description in [('audit-html', 'HTML 게임 검사'), ('audit-json', 'JSON 검사'),
                                  ('audit-text', '텍스트 통계')]:
            with self.subTest(slug=slug):
                self.create(slug, description)
                result = forge._test({'project_name': slug})
                self.assertTrue(result['passed'])
                self.assertEqual(result['compat_smoke_test'], 'passed')
                self.assertEqual(result['official_sdk'], 'not-run: Python mcp SDK not installed')
                self.assertTrue(all(result['checks'].values()))
                package = forge._package({'project_name': slug})
                self.assertTrue(Path(package['path']).exists())
                self.assertTrue(package['sha256'])
                with self.assertRaises(ValueError):
                    forge._package({'project_name': slug})

    def test_add_tool_preserves_prior_and_increments_version(self):
        self.create()
        out = forge._add_tool({'project_name': 'sample-html', 'description': 'JSON 검증'})
        self.assertEqual(out['version'], '0.2.1')
        self.assertTrue(Path(out['backup_path']).exists())
        self.assertEqual(out['tools'], ['html_audit', 'json_audit'])
        result = forge._test({'project_name': 'sample-html'})
        self.assertTrue(all(result['checks'].values()))
        out2 = forge._add_tool({'project_name': 'sample-html', 'description': '텍스트 통계'})
        self.assertEqual(out2['version'], '0.2.2')
        self.assertEqual(len(forge._validated('sample-html')[2]), 3)
        self.assertTrue(Path(forge._package({'project_name': 'sample-html'})['path']).exists())
        with self.assertRaises(ValueError):
            forge._add_tool({'project_name': 'sample-html', 'description': 'JSON 검사'})

    def test_tamper_does_not_mutate_original(self):
        self.create()
        path = forge._path('sample-html') / 'server.py'
        path.write_text(path.read_text() + '\n# modified')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            forge._add_tool({'project_name': 'sample-html', 'description': 'JSON 검사'})
        self.assertIn('# modified', path.read_text())

    def test_refuse_undeclared_files_and_symlinks(self):
        self.create()
        folder = forge._path('sample-html')
        (folder / 'mcp.py').write_text('print("shadow")')
        with self.assertRaisesRegex(ValueError, 'Unexpected or missing'):
            forge._test({'project_name': 'sample-html'})
        (folder / 'mcp.py').unlink()
        (folder / 'templates.py').unlink()
        (folder / 'templates.py').symlink_to(ROOT / 'templates.py')
        with self.assertRaisesRegex(ValueError, 'unsafe file'):
            forge._test({'project_name': 'sample-html'})

    def test_legacy_v01_migration(self):
        name = 'legacy-audit'
        folder = forge.PROJECTS / name
        folder.mkdir(parents=True)
        for filename in ('mcp_runtime.py', 'templates.py'):
            shutil.copyfile(ROOT / filename, folder / filename)
        old_server = ('from mcp_runtime import serve\nfrom templates import get_tool\n'
                      'serve("legacy-audit", "0.1.0", [get_tool("html_audit")])\n')
        (folder / 'server.py').write_text(old_server)
        old_manifest = {'name': name, 'version': '0.1.0', 'description': 'HTML 검사',
                        'template': 'html_audit',
                        'files_sha256': {n: hashlib.sha256((folder / n).read_bytes()).hexdigest()
                                         for n in forge.SOURCES}}
        (folder / 'manifest.json').write_text(json.dumps(old_manifest))
        (folder / 'README.md').write_text('legacy')
        self.assertEqual(forge._validated(name)[2], ['html_audit'])
        out = forge._add_tool({'project_name': name, 'description': 'JSON 검사'})
        self.assertEqual(out['version'], '0.2.0')
        self.assertEqual(forge._validated(name)[2], ['html_audit', 'json_audit'])
        self.assertEqual(forge._validated(name)[1]['previous_version'], '0.1.0')
        self.assertEqual(forge._validated(name)[1]['previous_manifest_sha256'],
                         hashlib.sha256((Path(out['backup_path']) / 'manifest.json').read_bytes()).hexdigest())

    @unittest.skipUnless(namespace_ready(), 'Linux user/mount/net namespaces are not supported')
    def test_namespace_network_and_project_readonly(self):
        folder = Path(self.tmp.name) / 'sandbox-probe'
        folder.mkdir()
        (folder / 'server.py').write_text('''import socket
from pathlib import Path
try:
    Path(__file__).with_name('blocked.txt').write_text('oops')
    print('PROJECT_WRITABLE')
except OSError:
    print('PROJECT_READONLY')
try:
    socket.create_connection(('1.1.1.1', 80), timeout=0.3)
    print('NETWORK_OK')
except OSError:
    print('NETWORK_BLOCKED')
''')
        result, isolation = run_server(folder, '', 'strict')
        self.assertIn('PROJECT_READONLY', result)
        self.assertIn('NETWORK_BLOCKED', result)
        self.assertNotIn('NETWORK_OK', result)
        self.assertTrue(isolation.startswith('linux-'))

    def test_strict_fails_closed_when_unavailable(self):
        self.create()
        from unittest.mock import patch
        with patch('sandbox.namespace_ready', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'fails closed'):
                forge._test({'project_name': 'sample-html', 'isolation': 'strict'})

    def test_concurrent_lock_refusal(self):
        self.create()
        lock = forge.PROJECTS / '.locks' / 'sample-html'
        lock.mkdir()
        try:
            with self.assertRaisesRegex(RuntimeError, 'locked'):
                forge._add_tool({'project_name': 'sample-html', 'description': 'JSON 검사'})
        finally:
            lock.rmdir()
        self.assertEqual(forge._validated('sample-html')[2], ['html_audit'])

    def test_old_functions_regression(self):
        issues = html_audit({'content': '<html><body><img src="http://a.com/x.png"></body></html>'})
        self.assertIn('missing-viewport', [x['code'] for x in issues['issues']])
        self.assertFalse(json_audit({'content': '{x}'})['valid'])

    def test_forge_stdio_roundtrip(self):
        messages = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2026-07-28', 'capabilities': {}, 'clientInfo': {'name': 'smoke', 'version': '1'}}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'forge_preview', 'arguments': {'description': 'HTML 검사'}}},
        ]
        wire = ''.join(json.dumps(m, ensure_ascii=False) + '\n' for m in messages)
        p = subprocess.run([sys.executable, '-S', '-B', str(ROOT / 'forge.py')], input=wire,
                           text=True, capture_output=True, timeout=5, cwd=ROOT)
        self.assertEqual(p.returncode, 0, p.stderr)
        data = {row['id']: row for row in (json.loads(line) for line in p.stdout.splitlines())}
        self.assertEqual(data[1]['result']['serverInfo']['version'], '0.4.0')
        self.assertEqual(len(data[2]['result']['tools']), 10)
        self.assertTrue(json.loads(data[3]['result']['content'][0]['text'])['supported'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
