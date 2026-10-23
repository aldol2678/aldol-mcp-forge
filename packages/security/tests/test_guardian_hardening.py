"""Deterministic adversarial tests using temporary, synthetic inputs only."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import secret_guardian as g
import guardian_io as gio


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        env = patch.dict(os.environ, {"ALDOL_SECURITY_ROOT": str(self.root)})
        env.start()
        self.addCleanup(env.stop)
        clock = patch.object(g, "_now", return_value=dt.date(2026, 10, 23))
        clock.start()
        self.addCleanup(clock.stop)

    def metadata(self, records):
        (self.root / g.MANIFEST).write_text(json.dumps({"schema_version": 1, "credentials": records}))

    def dotenv(self, content="OPENAI_API_KEY=SYNTHETIC_VALUE_ONLY\n"):
        path = self.root / ".env"
        path.write_text(content)
        path.chmod(0o600)
        return path

    def test_all_risk_priorities(self):
        self.metadata([{"ref": "synthetic", "privilege": "admin", "exposure_status": "confirmed",
                        "expires_at": "2026-10-23", "last_rotated_at": "2026-01-01",
                        "rotation_policy_days": 90}, {"ref": "unknown"}])
        self.dotenv().chmod(0o644)
        result = g.report()
        self.assertEqual({i['code']: i['severity'] for i in result['risks']}, {
            'USER_REPORTED_EXPOSURE': 'CRITICAL', 'EXPIRED_BY_METADATA': 'HIGH',
            'ROTATION_OVERDUE_BY_METADATA': 'MEDIUM', 'BROAD_PRIVILEGE_REVIEW': 'MEDIUM',
            'ROTATION_DATE_UNKNOWN': 'LOW', 'OWNER_UNKNOWN': 'LOW', 'DOTENV_WORLD_READABLE': 'HIGH'})
        self.assertEqual(result['coverage']['metadata_assurance'], 'user_reported_unverified')

    def test_dates_boundary_and_missing_expiry(self):
        self.metadata([{'ref': 'synthetic', 'owner': 'team', 'last_rotated_at': '2026-10-01',
                        'rotation_policy_days': 22}])
        result = g.report()
        self.assertEqual(result['status'], 'INVENTORIED')
        self.assertIn('expires_at', result['records'][0]['unknown_metadata'])
        self.assertEqual(result['coverage']['unknown_metadata_records'], 1)
        self.assertEqual(result['risks'], [])

    def test_names_never_imply_exposure(self):
        self.dotenv('LEAKED_PRODUCTION_TOKEN=SYNTHETIC_ONLY\n')
        self.assertEqual(g.report()['risks'], [])

    def test_report_scoped_refs_and_internal_links(self):
        self.metadata([{'ref': 'guessable-alias'}])
        self.dotenv()
        one, two = g.report(), g.report()
        refs = {r['credential_ref'] for r in one['records']}
        self.assertTrue(refs.isdisjoint(r['credential_ref'] for r in two['records']))
        self.assertTrue(all(i['credential_ref'] in refs for i in one['risks']))
        for old in (hashlib.sha256(b'guessable-alias').hexdigest()[:16],
                    hashlib.sha256(b'.env\0OPENAI_API_KEY').hexdigest()[:16]):
            self.assertNotIn(old, json.dumps(one))
        self.assertEqual(one['reference_scope'], 'report')
        for record in one['records']:
            self.assertRegex(record['credential_ref'], r'^(meta|env)-[a-f0-9]{16}$')

    def test_invalid_metadata_matrix(self):
        for item in ({'provider': []}, {'environment': {}}, {'privilege': 1},
                     {'owner': 'bad owner'}, {'expires_at': '2026-02-30'},
                     {'last_rotated_at': '2099-01-01'}, {'rotation_policy_days': True},
                     {'rotation_policy_days': 0}, {'rotation_policy_days': 3651},
                     {'exposure_status': 'verified'}, {'secret': 'SYNTHETIC_DO_NOT_ECHO'}):
            with self.subTest(fields=list(item)):
                self.metadata([{'ref': 'synthetic', **item}])
                result = g.report()
                self.assertEqual(result['status'], 'INCOMPLETE')
                self.assertFalse(result['coverage']['metadata_valid'])
                self.assertNotIn('SYNTHETIC_DO_NOT_ECHO', json.dumps(result))

    def test_malformed_json_matrix(self):
        for raw in ('{', '{"schema_version":true,"credentials":[]}',
                    '{"schema_version":1,"schema_version":1,"credentials":[]}',
                    '{"schema_version":1,"credentials":NaN}', '[' * 1100 + ']' * 1100,
                    '{"schema_version":1,"credentials":[]}' + ' ' * 65536):
            (self.root / g.MANIFEST).write_text(raw)
            self.assertEqual(g.report()['status'], 'INCOMPLETE')

    def test_duplicate_alias_and_record_limit(self):
        for records in ([{'ref': 'same'}, {'ref': 'same'}],
                        [{'ref': f'item-{i}'} for i in range(g.MAX_ITEMS + 1)]):
            self.metadata(records)
            self.assertEqual(g.report()['status'], 'INCOMPLETE')

    def test_total_record_limit_and_risk_truncation(self):
        self.metadata([{'ref': f'item-{i}'} for i in range(g.MAX_ITEMS)])
        self.dotenv()
        result = g.report()
        self.assertEqual(result['status'], 'FINDINGS_WITH_GAPS')
        self.assertEqual(result['credential_count'], g.MAX_ITEMS)
        self.assertEqual(len(result['risks']), g.MAX_ISSUES)
        self.assertFalse(result['coverage']['complete_within_local_scope'])

    def test_truncation_keeps_highest_priority_risks(self):
        self.metadata([{'ref': f'item-{i}'} for i in range(299)] + [
            {'ref': 'last', 'exposure_status': 'suspected'}])
        result = g.report()
        self.assertEqual(result['status'], 'FINDINGS_WITH_GAPS')
        self.assertEqual(result['risks'][0]['code'], 'USER_REPORTED_EXPOSURE')
        self.assertEqual(len(result['risks']), g.MAX_ISSUES)

    def test_dotenv_directory_is_not_complete(self):
        (self.root / '.env').mkdir()
        self.assertEqual(g.report()['status'], 'INCOMPLETE')

    def test_file_count_size_entries_and_depth_limits(self):
        self.dotenv('OPENAI_API_KEY=' + 'x' * 131072)
        self.assertEqual(g.report()['status'], 'INCOMPLETE')
        self.dotenv()
        (self.root / '.env.test').write_text('TOKEN=synthetic\n')
        with patch.object(g, 'MAX_ENV_FILES', 1):
            result = g.report()
            self.assertFalse(result['coverage']['complete_within_local_scope'])
            self.assertEqual(result['coverage']['dotenv_files_scanned'], 1)
        with patch.object(g, 'MAX_ENTRIES', 1):
            self.assertFalse(g.report()['coverage']['complete_within_local_scope'])
        current = self.root
        for _ in range(66):
            current = current / 'd'
            current.mkdir()
        self.assertFalse(g.report()['coverage']['complete_within_local_scope'])

    def test_fifo_hardlink_and_dangling_symlink(self):
        os.mkfifo(self.root / '.env')
        self.assertEqual(g.report()['status'], 'INCOMPLETE')
        (self.root / '.env').unlink()
        source = self.root / 'synthetic'
        source.write_text('TOKEN=synthetic\n')
        os.link(source, self.root / '.env')
        self.assertEqual(g.report()['status'], 'INCOMPLETE')
        (self.root / '.env').unlink()
        (self.root / '.env').symlink_to(self.root / 'missing')
        self.assertEqual(g.report()['status'], 'BLOCKED')

    def test_symlink_subpath_inside_root_rejected(self):
        (self.root / 'real').mkdir()
        (self.root / 'alias').symlink_to(self.root / 'real')
        self.assertEqual(g.report('alias')['status'], 'BLOCKED')

    def test_file_swap_between_stat_and_open(self):
        for kind in ('regular', 'symlink', 'fifo'):
            path = self.dotenv()
            replacement = self.root / 'replacement'
            replacement.write_text('TOKEN=synthetic_replacement\n')
            real_open = os.open
            def swap(name, flags, *args, **kwargs):
                if name == '.env':
                    path.unlink()
                    if kind == 'regular':
                        replacement.rename(path)
                    elif kind == 'symlink':
                        path.symlink_to(replacement)
                    else:
                        os.mkfifo(path)
                return real_open(name, flags, *args, **kwargs)
            with gio.workspace(self.root) as fd, patch.object(gio.os, 'open', side_effect=swap), \
                    patch.object(gio.os, 'read') as read:
                with self.assertRaises(OSError):
                    gio.read_file(fd, '.env', 131072)
                read.assert_not_called()
            path.unlink()

    def test_directory_swap_to_external_symlink(self):
        child = self.root / 'child'
        child.mkdir()
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / '.env').write_text('TOKEN=synthetic_external\n')
            real_open = os.open
            def swap(name, flags, *args, **kwargs):
                if name == 'child':
                    child.rmdir()
                    child.symlink_to(outside)
                return real_open(name, flags, *args, **kwargs)
            with patch.object(gio.os, 'open', side_effect=swap):
                result = g.report()
            self.assertEqual(result['status'], 'INCOMPLETE')
            self.assertEqual(result['credential_count'], 0)

    def test_growing_or_replaced_file_during_read(self):
        for replace in (False, True):
            path = self.dotenv()
            real_read = os.read
            changed = False
            total = 0
            def mutate(fd, amount):
                nonlocal changed, total
                data = real_read(fd, amount)
                total += len(data)
                if not changed:
                    changed = True
                    if replace:
                        path.unlink()
                        path.write_text('TOKEN=synthetic_replaced\n')
                    else:
                        with path.open('ab') as stream:
                            stream.write(b'x' * 150000)
                return data
            with patch.object(gio.os, 'read', side_effect=mutate):
                result = g.report()
            self.assertEqual(result['status'], 'INCOMPLETE')
            self.assertLessEqual(total, 131073)
            self.assertEqual(result['credential_count'], 0)

    def test_read_and_walk_errors_are_incomplete(self):
        self.dotenv()
        with patch.object(g, 'read_file', side_effect=PermissionError('SYNTHETIC_INTERNAL_PATH')):
            result = g.report()
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertNotIn('SYNTHETIC_INTERNAL_PATH', json.dumps(result))
        with patch.object(g.os, 'scandir', side_effect=PermissionError('private')):
            self.assertEqual(g.report()['status'], 'INCOMPLETE')

    def test_manifest_disappearance_is_incomplete(self):
        self.metadata([])
        def disappear(*args):
            (self.root / g.MANIFEST).unlink()
            raise FileNotFoundError('synthetic')
        with patch.object(g, 'read_file', side_effect=disappear):
            result = g.report()
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertTrue(result['coverage']['metadata_manifest_present'])

    def test_directory_change_during_inspection_is_incomplete(self):
        self.dotenv()
        original = g.read_file
        def mutate(fd, name, limit):
            result = original(fd, name, limit)
            (self.root / 'new-file').write_text('synthetic')
            return result
        with patch.object(g, 'read_file', side_effect=mutate):
            self.assertEqual(g.report()['status'], 'INCOMPLETE')

    def test_workspace_bytes_modes_names_and_mtime_unchanged(self):
        self.dotenv()
        self.metadata([{'ref': 'synthetic'}])
        def snapshot():
            return {p.name: (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns)
                    for p in self.root.iterdir()}
        before = snapshot()
        g.report()
        self.assertEqual(before, snapshot())
