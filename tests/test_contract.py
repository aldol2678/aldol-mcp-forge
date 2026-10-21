"""Regression tests for v0.4 declarative MCP contract scaffolds."""
import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import forge
from contract_forge import parse_contract, render_server


class ContractForgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = forge.PROJECTS, forge.PACKAGES, forge.HISTORY
        forge.PROJECTS = Path(self.tmp.name) / 'projects'
        forge.PACKAGES = Path(self.tmp.name) / 'packages'
        forge.HISTORY = Path(self.tmp.name) / 'history'

    def tearDown(self):
        forge.PROJECTS, forge.PACKAGES, forge.HISTORY = self.old
        self.tmp.cleanup()

    def contract(self, org='seum'):
        return (ROOT / 'examples' / (org + '-mcp-contract.json')).read_text(encoding='utf-8')

    def test_all_three_enterprises_can_generate_test_and_package(self):
        for org in ('seum', 'bonsae', 'majung'):
            with self.subTest(org=org):
                name = org + '-scaffold'
                spec = self.contract(org)
                preview = forge._preview_contract({'contract_json': spec})
                self.assertTrue(preview['supported'])
                self.assertFalse(preview['handlers_implemented'])
                created = forge._create_contract({'project_name': name, 'contract_json': spec})
                self.assertTrue(created['created'])
                self.assertFalse(created['auto_deployed'])
                folder, manifest, contract = forge._validated_contract(name)
                self.assertEqual(manifest['kind'], 'declarative-scaffold')
                self.assertEqual(manifest['version'], '0.4.0')
                self.assertEqual([t['name'] for t in contract['tools']], created['tools'])
                ast.parse((folder / 'server.py').read_text(encoding='utf-8'))
                result = forge._test({'project_name': name})
                self.assertTrue(result['passed'])
                self.assertTrue(all(result['checks'].values()))
                self.assertFalse(result['handlers_implemented'])
                self.assertFalse(result['implementation_verified'])
                self.assertEqual(result['official_sdk'], 'not-run: scaffold only')
                out = forge._package({'project_name': name})
                with ZipFile(out['path']) as archive:
                    self.assertIn(name + '/contract.json', archive.namelist())
                    self.assertIn(name + '/server.py', archive.namelist())
                    self.assertIn(name + '/requirements.txt', archive.namelist())
                with self.assertRaisesRegex(ValueError, 'exists'):
                    forge._create_contract({'project_name': name, 'contract_json': spec})
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    forge._package({'project_name': name})

    def test_read_only_preview(self):
        forge._preview_contract({'contract_json': self.contract()})
        self.assertFalse(forge.PROJECTS.exists())

    def test_invalid_fields_fail_closed(self):
        sample = json.loads(self.contract())
        variants = []
        for bad_name in ('__import__', 'a();exit()', 'app'):
            obj = json.loads(self.contract())
            obj['tools'][0]['name'] = bad_name
            variants.append(obj)
        obj = json.loads(self.contract())
        obj['tools'][0]['inputs'][0]['type'] = 'exec'
        variants.append(obj)
        obj = json.loads(self.contract())
        obj['tools'][0]['output_schema']['$ref'] = 'https://evil.example/schema'
        variants.append(obj)
        obj = json.loads(self.contract())
        obj['tools'][0]['inputs'][0]['required'] = 'true'
        variants.append(obj)
        obj = json.loads(self.contract())
        obj['tools'] = obj['tools'] * 5
        variants.append(obj)
        for doc in variants:
            with self.subTest(doc=doc['tools'][0]['name']), self.assertRaises(ValueError):
                parse_contract(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
            parse_contract('{"tools":[],"tools":[]}')

    def test_injection_is_inert_and_handlers_fail_closed(self):
        doc = json.loads(self.contract())
        doc['tools'][0]['description'] = '"""' + '\nimport os; os.system("touch /tmp/pwned")'
        source = render_server('safe-demo', parse_contract(json.dumps(doc))['tools'])
        ast.parse(source)
        self.assertNotIn('\nimport os; os.system', source)
        self.assertIn('NOT_IMPLEMENTED', source)
        self.assertNotIn('subprocess', source)

    def test_tampering_and_symlinks_are_rejected(self):
        forge._create_contract({'project_name': 'seum-scaffold', 'contract_json': self.contract()})
        folder = forge._path('seum-scaffold')
        source = folder / 'server.py'
        source.write_text(source.read_text() + '\n# compromise')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            forge._test({'project_name': 'seum-scaffold'})
        source.write_text(source.read_text().replace('\n# compromise', ''))
        self.assertTrue(forge._test({'project_name': 'seum-scaffold'})['passed'])
        source.unlink()
        source.symlink_to(ROOT / 'contract_forge.py')
        with self.assertRaisesRegex(ValueError, 'unsafe file'):
            forge._test({'project_name': 'seum-scaffold'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
