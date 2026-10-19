"""Regression, OpenAPI parsing, tamper detection, and offline protocol tests."""
import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import forge
from api_runtime import call_operation
from openapi_forge import parse_openapi, render_server


def sample_spec():
    return {
        'openapi': '3.1.0', 'info': {'title': 'Pets'},
        'paths': {
            '/pets': {
                'get': {'operationId': 'list_pets', 'summary': 'List available pets',
                        'parameters': [{'name': 'limit', 'in': 'query', 'schema': {'type': 'integer'}}]},
                'post': {'operationId': 'create_pet'},
            },
            '/pets/{pet_id}': {
                'get': {'operationId': 'get_pet', 'summary': 'Get one pet',
                        'parameters': [{'name': 'pet_id', 'in': 'path', 'required': True,
                                        'schema': {'type': 'string'}}]}
            }
        }
    }


class OpenAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = forge.PROJECTS, forge.PACKAGES, forge.HISTORY
        forge.PROJECTS = Path(self.temp.name) / 'projects'
        forge.PACKAGES = Path(self.temp.name) / 'packages'
        forge.HISTORY = Path(self.temp.name) / 'history'
        self.spec = json.dumps(sample_spec())

    def tearDown(self):
        forge.PROJECTS, forge.PACKAGES, forge.HISTORY = self.old
        self.temp.cleanup()

    def import_it(self):
        return forge._import_openapi({'project_name': 'pets-readonly', 'spec_json': self.spec})

    def test_preview_is_read_only(self):
        out = forge._preview_openapi({'spec_json': self.spec})
        self.assertEqual(out['operations'], ['list_pets', 'get_pet'])
        self.assertEqual(out['skipped'][0]['method'], 'POST')
        self.assertFalse(forge.PROJECTS.exists())

    def test_create_run_package_with_readme_and_requirements(self):
        created = self.import_it()
        self.assertTrue(created['created'])
        self.assertFalse(created['auto_deployed'])
        self.assertEqual(created['tools'], ['list_pets', 'get_pet'])
        folder, manifest, parsed = forge._validated_openapi('pets-readonly')
        self.assertEqual(manifest['kind'], 'openapi-get')
        result = forge._test({'project_name': 'pets-readonly'})
        self.assertTrue(all(result['checks'].values()))
        self.assertFalse(result['default_network_access'])
        self.assertEqual(result['sample_tool_results']['get_pet']['path'], '/pets/demo')
        packaged = forge._package({'project_name': 'pets-readonly'})
        from zipfile import ZipFile
        with ZipFile(packaged['path']) as zipfile:
            self.assertIn('pets-readonly/requirements.txt', zipfile.namelist())
            self.assertIn('pets-readonly/api_runtime.py', zipfile.namelist())
        with self.assertRaisesRegex(ValueError, 'exists'):
            self.import_it()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            forge._package({'project_name': 'pets-readonly'})

    def test_reject_reference_and_unsafe_parameters(self):
        specs = []
        for mutation in ('ref', 'delete_only', 'unsafe_id', 'reserved_id', 'unsafe_path', 'array', 'header', 'path_missing'):
            doc = sample_spec()
            if mutation == 'ref':
                doc['paths']['/pets']['get']['parameters'] = [{'$ref': '#/components/parameters/limit'}]
            elif mutation == 'delete_only':
                doc['paths'] = {'/secrets': {'delete': {'operationId': 'nuke'}}}
            elif mutation == 'unsafe_id':
                doc['paths']['/pets']['get']['operationId'] = 'run();open("x")'
            elif mutation == 'reserved_id':
                doc['paths']['/pets']['get']['operationId'] = 'app'
            elif mutation == 'unsafe_path':
                doc['paths']['/../etc/passwd'] = doc['paths'].pop('/pets')
            elif mutation == 'array':
                doc['paths']['/pets']['get']['parameters'][0]['schema']['type'] = 'array'
            elif mutation == 'header':
                doc['paths']['/pets']['get']['parameters'][0]['in'] = 'header'
            elif mutation == 'path_missing':
                doc['paths']['/pets/{pet_id}']['get']['parameters'] = []
            specs.append(doc)
        for doc in specs:
            with self.subTest(doc=doc), self.assertRaises(ValueError):
                parse_openapi(json.dumps(doc))

    def test_operation_sanitizes_path_value_and_dry_run(self):
        op = parse_openapi(self.spec)['operations'][1]
        with patch.dict(os.environ, {'ALDOL_API_BASE_URL': '', 'ALDOL_API_ALLOWED_HOST': ''}):
            response = call_operation(op, {'pet_id': '../x?auth=1'})
        self.assertEqual(response['path'], '/pets/..%2Fx%3Fauth%3D1')
        self.assertFalse(response['network_called'])
        with self.assertRaises(ValueError):
            call_operation(op, {'pet_id': 2})
        with self.assertRaises(ValueError):
            call_operation(op, {})

    def test_external_network_requires_allowlist(self):
        op = parse_openapi(self.spec)['operations'][0]
        for base, host in [('http://api.example.com', 'api.example.com'),
                           ('https://api.example.com', ''),
                           ('https://127.0.0.1', '127.0.0.1'),
                           ('https://api.example.com', 'different.example.com')]:
            with self.subTest(base=base, host=host):
                with patch.dict(os.environ, {'ALDOL_API_BASE_URL': base, 'ALDOL_API_ALLOWED_HOST': host}):
                    with self.assertRaisesRegex(ValueError, 'HTTPS public host'):
                        call_operation(op, {})

    def test_tamper_and_symlink_guard(self):
        self.import_it()
        f = forge._path('pets-readonly') / 'server.py'
        f.write_text(f.read_text() + '\n# injected')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            forge._test({'project_name': 'pets-readonly'})
        f.write_text(f.read_text().replace('\n# injected', ''))
        self.assertTrue(forge._test({'project_name': 'pets-readonly'})['passed'])
        f.unlink()
        f.symlink_to(ROOT / 'openapi_forge.py')
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            forge._test({'project_name': 'pets-readonly'})

    def test_description_source_injection_stays_inert(self):
        doc = sample_spec()
        doc['paths']['/pets']['get']['summary'] = '"""\\\nimport os; os.system("touch /tmp/forged")\n"""'
        ops = parse_openapi(json.dumps(doc))['operations']
        source = render_server('safe-name', '0.3.0', ops)
        ast.parse(source)
        self.assertNotIn('    import os; os.system(', source)

    def test_legacy_v02_patch_package_contains_requirements(self):
        forge._create({'project_name': 'legacy-html', 'description': 'HTML 검사'})
        forge._add_tool({'project_name': 'legacy-html', 'description': 'JSON 검사'})
        out = forge._package({'project_name': 'legacy-html'})
        from zipfile import ZipFile
        with ZipFile(out['path']) as archive:
            self.assertIn('legacy-html/requirements.txt', archive.namelist())

    def test_forge_stdio_advertises_import_tools(self):
        wire = ''.join(json.dumps(m) + '\n' for m in (
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}},
        ))
        p = subprocess.run([sys.executable, '-B', str(ROOT / 'forge.py')], cwd=ROOT,
                           input=wire, text=True, capture_output=True, timeout=5)
        self.assertEqual(p.returncode, 0, p.stderr)
        data = {obj['id']: obj for obj in (json.loads(line) for line in p.stdout.splitlines())}
        self.assertEqual(data[1]['result']['serverInfo']['version'], '0.3.1')
        names = [tool['name'] for tool in data[2]['result']['tools']]
        self.assertEqual(len(names), 8)
        self.assertIn('forge_import_openapi', names)


if __name__ == '__main__':
    unittest.main(verbosity=2)
