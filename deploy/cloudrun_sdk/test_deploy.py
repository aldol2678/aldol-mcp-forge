"""Deployment must refuse unsafe inputs before making any cloud mutation."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
SCRIPT = Path(__file__).with_name('prepare_and_deploy.sh').resolve()
class DeploymentGuardTests(unittest.TestCase):
    def invoke(self, deploy=False, **values):
        with tempfile.TemporaryDirectory() as folder:
            fake = Path(folder) / 'gcloud'
            fake.write_text('#!/bin/sh\nprintf "gcloud-was-called\\n"\nexit 0\n')
            fake.chmod(0o700)
            env = {'PATH':folder+':/usr/bin:/bin', **values}
            return subprocess.run(['bash', str(SCRIPT), *(['--deploy'] if deploy else [])], env=env, text=True, capture_output=True)
    def test_dry_run_needs_neither_credentials_nor_region(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('gcloud-was-called', result.stdout)
    def test_deploy_refuses_default_runtime_identity(self):
        result = self.invoke(True, REGION='asia-northeast3', FORGE_SDK_SECRET_REF='forge-sdk-hmac:1')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('gcloud-was-called', result.stdout)
    def test_deploy_refuses_slack_named_secret(self):
        result = self.invoke(True, REGION='asia-northeast3', FORGE_SERVICE_ACCOUNT='forge-sdk-verifier@aram-slack-bridge-2026.iam.gserviceaccount.com',FORGE_SDK_SECRET_REF='slack-signing-secret:latest')
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn('gcloud-was-called', result.stdout)
if __name__ == '__main__': unittest.main()
