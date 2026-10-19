"""Verifier control-flow checks; never count as actual SDK integration."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verify_sdk import expected_tools, force_dry_run


class SDKVerifierContractTests(unittest.TestCase):
    def test_openapi_expected_tools_are_read_only(self):
        manifest = json.loads((ROOT / 'workspace/projects/aldol-openapi-pets/manifest.json').read_text())
        names, args = expected_tools(manifest)
        self.assertEqual(names, ['list_pets', 'get_pet'])
        self.assertEqual(args['get_pet'], {'pet_id': 'sample'})

    def test_write_method_rejected(self):
        with self.assertRaisesRegex(ValueError, 'read-only'):
            expected_tools({'kind': 'openapi-get', 'operations': [
                {'name': 'delete_thing', 'method': 'DELETE', 'parameters': []}]})

    def test_dry_run_process_environment_restored(self):
        import os
        old = os.environ.get('ALDOL_API_BASE_URL')
        try:
            os.environ['ALDOL_API_BASE_URL'] = 'https://example.com'
            with force_dry_run():
                self.assertNotIn('ALDOL_API_BASE_URL', os.environ)
            self.assertEqual(os.environ['ALDOL_API_BASE_URL'], 'https://example.com')
        finally:
            if old is None:
                os.environ.pop('ALDOL_API_BASE_URL', None)
            else:
                os.environ['ALDOL_API_BASE_URL'] = old

    def test_official_sdk_unavailable_is_not_reported_as_success(self):
        # This environment currently does not have the SDK. Don't fake a pass.
        import importlib.metadata
        try:
            importlib.metadata.version('mcp')
        except importlib.metadata.PackageNotFoundError:
            run = subprocess.run([sys.executable, str(ROOT / 'verify_sdk.py'),
                                  str(ROOT / 'workspace/projects/aldol-openapi-pets')],
                                 capture_output=True, text=True, timeout=8)
            self.assertEqual(run.returncode, 2)
            payload = json.loads(run.stdout)
            self.assertFalse(payload['passed'])
            self.assertFalse(payload['official_sdk_tested'])
        else:
            self.skipTest('SDK is installed; use real SDK verifier')
