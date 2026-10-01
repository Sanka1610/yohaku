"""Candidate A offline release consistency and public output privacy regression."""

from copy import deepcopy
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('candidate_a', ROOT / 'scripts/check_candidate_a.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class CandidateAReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = check.load_json(ROOT / check.DATA / 'candidate-a-scope.json')
        cls.index = check.load_json(ROOT / check.DATA / 'candidate-a-evidence.json')
        cls.drift = check.load_json(ROOT / check.DATA / 'stage1-source-drift.json')
        cls.promotion = check.load_json(ROOT / check.DATA / 'promotion-source-review.json')
        cls.documents = {p: (ROOT / p).read_text() for p in check.DOCS + [check.TASK_DOC, check.POLICY]}

    def test_current_candidate_a(self):
        self.assertTrue(check.validate().startswith('PASS:'))
        self.assertEqual(check.main(), 0)

    def test_claim_mismatches(self):
        cases = {'runtime_exact_version': '0.159.0', 'support_profile_id': 'wrong-profile',
                 'mapping_key': 'C-REF-M', 'runtime_family': 'hermes', 'surface': 'CLI',
                 'task_profile_id': 'different-task', 'operational_launcher_support': False,
                 'task_runner_support': False, 'accepted_endpoint': 'ROLLOVER_OBSERVED',
                 'maturity': 'experimental', 'release_channel': 'undeclared', 'known_exclusions': []}
        for field, value in cases.items():
            with self.subTest(field=field):
                scope = deepcopy(self.scope)
                scope['profiles'][1][field] = value
                with self.assertRaises(check.Invalid):
                    check.validate(scope=scope)

    def test_missing_or_mismatched_evidence(self):
        for mutation in ('missing', 'endpoint', 'id', 'manifest'):
            with self.subTest(mutation=mutation):
                index = deepcopy(self.index)
                if mutation == 'missing':
                    index['records'].pop()
                elif mutation == 'manifest':
                    index['records'][1]['source_manifest_sha256'] = '0' * 64
                else:
                    field = 'accepted_endpoint' if mutation == 'endpoint' else 'evidence_record_id'
                    index['records'][1][field] = 'incorrect'
                with self.assertRaises(check.Invalid):
                    check.validate(index=index)

    def test_candidate_b_c_or_historical_scope_is_rejected(self):
        for profile in check.EXCLUDED:
            with self.subTest(profile=profile):
                scope = deepcopy(self.scope)
                scope['alpha_scope_profile_ids'].append(profile)
                with self.assertRaises(check.Invalid):
                    check.validate(scope=scope)

    def test_missing_excluded_family(self):
        scope = deepcopy(self.scope)
        scope['excluded_runtime_families'].remove('claude')
        with self.assertRaises(check.Invalid):
            check.validate(scope=scope)

    def test_registry_drift(self):
        for key, value in [('runtime_version', '0.159'), ('maturity', 'experimental'),
                           ('release_channel', 'undeclared'), ('entrypoint', 'start'),
                           ('known_limitations', []), ('evidence_id', 'missing')]:
            with self.subTest(field=key):
                profiles = deepcopy(check.PROFILES)
                profiles[check.IDS[1]][key] = value
                with self.assertRaises(check.Invalid):
                    check.validate(profiles=profiles)

    def test_every_canonical_table_is_checked(self):
        for path in self.documents:
            with self.subTest(path=path):
                docs = dict(self.documents)
                before, block = docs[path].split('<!-- candidate-a:start -->')
                docs[path] = before + '<!-- candidate-a:start -->' + block.replace('alpha', 'experimental')
                with self.assertRaises(check.Invalid):
                    check.validate(documents=docs)

    def test_editorial_wording_does_not_trigger_drift(self):
        docs = {p: text + '\nEditorial clarification outside the checked fields.\n'
                for p, text in self.documents.items()}
        self.assertTrue(check.validate(documents=docs).startswith('PASS:'))

    def test_historical_evidence_state_is_not_current_release_claim(self):
        self.assertEqual(self.scope['maturity'], 'alpha')
        self.assertEqual(self.scope['release_channel'], 'Alpha')
        for row in self.index['records']:
            self.assertEqual(row['maturity'], 'experimental')
            self.assertEqual(row['release_channel'], 'undeclared')
        index = deepcopy(self.index)
        index['records'][0]['maturity'] = 'alpha'
        with self.assertRaises(check.Invalid):
            check.validate(index=index)

    def test_excluded_profiles_cannot_be_promoted(self):
        for name in check.EXCLUDED:
            with self.subTest(profile=name):
                profiles = deepcopy(check.PROFILES)
                profiles[name]['maturity'] = 'alpha'
                with self.assertRaisesRegex(check.Invalid, 'EXCLUDED_PROFILE_DRIFT'):
                    check.validate(profiles=profiles)

    def test_promotion_review_and_source_hashes_are_fixed(self):
        for field in ('review_date', 'semantic_areas', 'reviewed_python_sha256'):
            promotion = deepcopy(self.promotion)
            if field == 'semantic_areas':
                promotion[field]['completion predicate'] = 'CHANGED'
            elif field == 'reviewed_python_sha256':
                promotion[field]['src/yohaku/profiles.py'] = '0' * 64
            else:
                promotion[field] = '2026-09-29'
            with self.subTest(field=field), self.assertRaises(check.Invalid):
                check.validate(promotion=promotion)

    def test_unreviewed_source_requires_review(self):
        original = Path.read_bytes
        target = ROOT / 'src/yohaku/document_review.py'
        def changed(path):
            return original(path) + (b'\n# source changed\n' if path == target else b'')
        with patch.object(Path, 'read_bytes', changed):
            with self.assertRaisesRegex(check.Invalid, 'SOURCE_REVIEW_REQUIRED'):
                check.validate()

    def test_rc_identity_source_changes_require_review(self):
        original = Path.read_bytes
        for name in ('operational_hosts.py', 'document_review_runtime.py'):
            target = ROOT / 'src/yohaku' / name
            def changed(path):
                return original(path) + (b'\n# unreviewed change\n' if path == target else b'')
            with self.subTest(name=name), patch.object(Path, 'read_bytes', changed):
                with self.assertRaisesRegex(check.Invalid, 'SOURCE_REVIEW_REQUIRED'):
                    check.validate()

    def test_license_metadata_drift_is_rejected(self):
        original = Path.read_text
        target = ROOT / 'pyproject.toml'
        for before, after in [('license = "Apache-2.0"', 'license = "MIT"'),
                              ('license-files = ["LICENSE"]', 'license-files = []')]:
            def changed(path, *args, **kwargs):
                data = original(path, *args, **kwargs)
                return data.replace(before, after) if path == target else data
            with self.subTest(field=before), patch.object(Path, 'read_text', changed):
                with self.assertRaisesRegex(check.Invalid, 'PACKAGE_LICENSE_DRIFT'):
                    check.validate()

    def test_modified_license_text_is_rejected(self):
        original = Path.read_bytes
        target = ROOT / 'LICENSE'
        def changed(path):
            return original(path) + (b'changed license text' if path == target else b'')
        with patch.object(Path, 'read_bytes', changed):
            with self.assertRaisesRegex(check.Invalid, 'LICENSE_TEXT_DRIFT'):
                check.validate()

    def test_duplicate_json_key_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'record.json'
            path.write_text('{"schema": 1, "schema": 1}')
            with self.assertRaises(check.Invalid):
                check.load_json(path)

    def test_private_fields_and_payloads_never_fit_public_allowlist(self):
        # Synthetic canaries only. No real private material is opened by this test.
        canaries = {
            'credential': 'synthetic-secret-value', 'auth.json': '{"access_token":"canary"}',
            'input_document': '# private input canary', 'report_body': '# private report canary',
            'exception': 'raw exception body canary', 'tool_argument': '{"input":"canary"}',
            'tool_result': '{"result":"canary"}', 'native_session_id': 'session-canary',
            'receipt_nonce': 'nonce-canary', 'maintainer_path': '/home/private-maintainer/canary',
            'private_workspace': '/private/workspace/canary',
        }
        for name, value in canaries.items():
            for label, original, template in [
                    ('scope', self.scope, check.scope_template()),
                    ('index', self.index, check.index_template()),
                    ('drift', self.drift, check.drift_template(ROOT)),
                    ('promotion', self.promotion, check.promotion_template(ROOT))]:
                with self.subTest(field=name, record=label):
                    data = deepcopy(original)
                    data[name] = value
                    with self.assertRaises(check.Invalid):
                        check.public_shape(data, template)
            for field in self.index['records'][0]:
                with self.subTest(payload=name, existing_field=field):
                    index = deepcopy(self.index)
                    index['records'][0][field] = value
                    with self.assertRaises(check.Invalid):
                        check.public_shape(index, check.index_template())
            # A private field nested in a permitted object must also fail.
            index = deepcopy(self.index)
            index['records'][0]['artifacts'][name] = value
            with self.assertRaises(check.Invalid):
                check.public_shape(index, check.index_template())

    def test_failure_exit_does_not_echo_payload(self):
        output = io.StringIO()
        with patch.object(check, 'validate', side_effect=ValueError('private-body-canary')):
            with redirect_stdout(output):
                self.assertEqual(check.main(), 1)
        self.assertNotIn('private-body-canary', output.getvalue())


if __name__ == '__main__':
    unittest.main()
