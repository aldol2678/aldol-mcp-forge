"""Security tests for downloaded Sites Studio ZIP validation.

The positive fixtures come from the actual JS Sites Worker exporter, not Python.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZIP_STORED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ci.verify_studio_archive import validated_archive, verify

FIXTURES = ROOT / "ci-results" / "studio-sdk-fixtures"


def rewrite_zip(path, mutate, addition=None, repair_hashes=False):
    with ZipFile(path) as original:
        entries = {name: original.read(name) for name in original.namelist()}
    entries[mutate] = entries[mutate] + b"\n# mutation"
    if addition:
        entries[addition] = b"malicious"
    if repair_hashes:
        manifest = json.loads(entries["manifest.json"])
        if mutate in manifest["files_sha256"]:
            manifest["files_sha256"][mutate] = hashlib.sha256(entries[mutate]).hexdigest()
            entries["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
        entries["SHA256SUMS"] = ("\n".join(
            hashlib.sha256(value).hexdigest() + "  " + name
            for name, value in entries.items() if name != "SHA256SUMS"
        ) + "\n").encode()
    with ZipFile(path, "w", ZIP_STORED) as z:
        for name, content in entries.items():
            z.writestr(name, content)


class StudioArchiveTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    def fixture(self, name="studio-curated-v021"):
        return FIXTURES / (name + ".zip")

    def project(self, name="studio-ci-curated"):
        target = self.root / "projects" / name
        target.mkdir(parents=True, exist_ok=True)
        return target

    def test_exact_generator_parity_accepts_curated_and_openapi(self):
        self.assertEqual(
            validated_archive(self.fixture(), self.project())["version"], "0.2.1"
        )
        self.assertEqual(
            validated_archive(
                self.fixture("studio-openapi-get"),
                self.project("studio-ci-openapi"),
            )["kind"], "openapi-get"
        )

    def test_reject_hash_mismatch(self):
        original = self.fixture()
        bad = self.root / "tampered.zip"
        bad.write_bytes(original.read_bytes())
        rewrite_zip(bad, "server.py")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            validated_archive(bad, self.project())

    def test_reject_executable_even_when_all_hashes_are_repaired(self):
        bad = self.root / "rehashed.zip"
        bad.write_bytes(self.fixture().read_bytes())
        rewrite_zip(bad, "server.py", repair_hashes=True)
        with self.assertRaises((ValueError, RuntimeError)):
            validated_archive(bad, self.project())

    def test_reject_traversal(self):
        bad = self.root / "traversal.zip"
        bad.write_bytes(self.fixture().read_bytes())
        rewrite_zip(bad, "README.md", addition="../outside.py", repair_hashes=True)
        with self.assertRaisesRegex(ValueError, "Unexpected ZIP member"):
            validated_archive(bad, self.project())
        self.assertFalse((self.root / "outside.py").exists())

    def test_reject_unknown_files(self):
        bad = self.root / "extra.zip"
        bad.write_bytes(self.fixture().read_bytes())
        rewrite_zip(bad, "README.md", addition="unsafe.py", repair_hashes=True)
        with self.assertRaisesRegex(ValueError, "Unexpected ZIP member"):
            validated_archive(bad, self.project())

    def test_real_official_sdk_both_transports(self):
        for name in ("studio-curated-v021", "studio-openapi-get"):
            with self.subTest(fixture=name):
                r = verify(str(self.fixture(name)))
                self.assertTrue(r["passed"], r)
                self.assertEqual(r["official_sdk"], "PASS")
                self.assertEqual(r["inmemory"], "PASS")
                self.assertEqual(r["stdio"], "PASS")
                self.assertFalse(r["network_used"])


if __name__ == "__main__":
    unittest.main()
