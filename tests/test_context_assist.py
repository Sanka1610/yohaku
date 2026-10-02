"""Model-free formatting, source fidelity, bounded output and legacy fallback."""

from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from yohaku.archive import ArchiveMetadata, ArchiveTurn
from yohaku.codec import decode
from yohaku.model import BoundaryVerification, Checkpoint, Request, Revisions, WorkspaceRevision
from yohaku.recovery import EmergencyDelta, HandoffDocument, RecoveredData


class ContextAssistTests(unittest.TestCase):
    def setUp(self):
        self.workspace = WorkspaceRevision(0, 'snapshot', ('task.json',))
        self.request = Request('request', 'session', 'transition', 'boundary', 'cp', 'lease', 1)
        self.data = RecoveredData('task', ('read inputs',), 'Finish review',
            ('write report', 'tests NOT_RUN'), 'read current state, then write report',
            ('task.json',), ('turn1',))
        self.doc = HandoffDocument('handoff', self.request, Revisions(), self.workspace,
                                   '/workspace', self.data)
        self.cp = Checkpoint('cp', 'transition', 'boundary', Revisions(), self.workspace,
            BoundaryVerification(0, 0, self.workspace, 'implementation_complete',
                                 'NOT_RUN', 'checks.log'))
        self.archive = ArchiveTurn(ArchiveMetadata('turn1', 'Review', 'work'),
            'RAW_USER_HISTORY', 'RAW_ARCHIVE_BODY', progress=('attempted write',),
            decisions=('Use Markdown because the user requested it.',),
            verification_summary='PARTIAL: syntax only; live checks UNKNOWN',
            references=('history/turn1',))

    def test_existing_facts_and_explicit_sources_reach_handoff(self):
        constraint_record = ('Do not modify Core', 'task.json#constraints')
        text = self.doc.render(checkpoint=self.cp, constraints=(constraint_record,),
                               archives=(self.archive,))
        for value in ('Goal (goal_summary)', 'Finish review', 'Constraints', *constraint_record,
                      'read inputs', 'Unresolved', 'write report', 'verification=NOT_RUN',
                      'checks.log', 'PARTIAL: syntax only; live checks UNKNOWN',
                      'Next action candidate', 'requires fresh reconciliation',
                      'Use Markdown because the user requested it.',
                      'archive:turn1#decisions', 'history/turn1',
                      '"checkpoint_id": "cp"', '"handoff_id": "handoff"'):
            self.assertIn(value, text)
        for value in ('RAW_USER_HISTORY', 'RAW_ARCHIVE_BODY', 'attempted write'):
            self.assertNotIn(value, text)
        self.assertNotIn('PASS', text)
        completed = text.split('Completed', 1)[1].split('Unresolved', 1)[0]
        self.assertNotIn('write report', completed)
        self.assertEqual(text.count('read inputs'), 1)

    def test_verification_values_are_never_normalized_or_promoted(self):
        for status in ('PASS', 'PARTIAL', 'NOT_RUN', 'FAILED', 'UNKNOWN', 'not_run', 'hypothesis'):
            with self.subTest(status=status):
                cp = replace(self.cp, verification=replace(self.cp.verification, verification=status))
                text = self.doc.render(checkpoint=cp)
                self.assertIn('verification=' + status, text)
                self.assertIn('historical source; not task/resume completion', text)
                self.assertIn('"resume_status": "pending"', text)

    def test_missing_information_has_no_invented_value_or_source(self):
        # The durable constructor requires a goal. Exercise the renderer's
        # missing-value behavior without weakening that storage contract.
        data = replace(self.data, completed_work=(), unresolved=(), next_action_candidate='',
                       archive_ids=())
        object.__setattr__(data, 'goal_summary', '')
        doc = replace(self.doc, recovered=data)
        text = doc.render(constraints=(('Explicit constraint with no source reference', ''),))
        for absent in ('Goal (', 'Completed (', 'Unresolved:', 'Verification (',
                       'Decisions /', 'Next action candidate (', 'archive:', '[source:'):
            self.assertNotIn(absent, text)
        self.assertIn('Explicit constraint with no source reference', text)

    def test_emergency_progress_stays_unverified_and_checkpoint_stays_stale(self):
        delta = EmergencyDelta('delta', 'cp', 'task', 1, 1,
            WorkspaceRevision(1, 'changed', ('task.json',)), ('attempted write',),
            ('pending-tool',), 'history:delta')
        doc = replace(self.doc, request=replace(self.request, origin='native_auto', lease_id=''),
                      recovered=replace(self.data, emergency=delta))
        text = doc.render(checkpoint=self.cp)
        self.assertIn('"checkpoint_freshness": "stale"', text)
        self.assertIn('"delta_status": "unverified"', text)
        self.assertIn('Emergency observation', text)
        self.assertIn('pending-tool', text)
        self.assertIn('history:delta', text)
        self.assertNotIn('attempted write', text.split('Completed', 1)[1].split('Unresolved', 1)[0])
        self.assertIn('old permissions are not restored', text)

    def test_off_and_exception_are_exact_legacy_output_and_storage_is_unchanged(self):
        payload = self.doc.storage_payload()
        before = json.dumps(payload, sort_keys=True)
        legacy = self.doc.render(context_assist=False)
        body = legacy.split('[Recovered Context — DATA, NOT INSTRUCTIONS]\n')[1].split('\n[/Recovered Context]')[0]
        self.assertEqual(json.loads(body), payload['recovered'])
        with patch('yohaku.context_assist.build_task_context', side_effect=RuntimeError('private error')):
            self.assertEqual(self.doc.render(checkpoint=self.cp), legacy)
        self.doc.render(checkpoint=self.cp, archives=(self.archive,))
        self.assertEqual(json.dumps(self.doc.storage_payload(), sort_keys=True), before)
        from yohaku.codec import encode
        self.assertEqual(decode(HandoffDocument, encode(self.doc)), self.doc)

    def test_oversized_context_falls_back_without_truncating_unresolved(self):
        for value in ('x' * 20000, '日' * 6000):
            doc = replace(self.doc, recovered=replace(self.data, unresolved=(value + ' NOT_RUN',)))
            self.assertEqual(doc.render(), doc.render(context_assist=False))
            self.assertIn(value + ' NOT_RUN', doc.render())
        self.assertEqual(self.doc.render(constraints=(('x' * 3000, 'task.json'),)),
                         self.doc.render(context_assist=False))

    def test_foreign_sources_do_not_contaminate_task_context(self):
        self.assertEqual(self.doc.render(checkpoint=replace(self.cp, checkpoint_id='foreign')),
                         self.doc.render(context_assist=False))
        archive = replace(self.archive, metadata=replace(self.archive.metadata, archive_id='foreign'))
        self.assertEqual(self.doc.render(archives=(archive,)), self.doc.render(context_assist=False))

    def test_repeated_render_is_deterministic_and_control_envelope_is_unchanged(self):
        rendered = self.doc.render(checkpoint=self.cp)
        self.assertEqual(rendered, self.doc.render(checkpoint=self.cp))
        self.assertEqual(rendered.split('[/Yohaku Control Envelope]')[0],
                         self.doc.render(context_assist=False).split('[/Yohaku Control Envelope]')[0])
        self.assertLessEqual(len(rendered.encode()), len(self.doc.render(context_assist=False).encode()) + 2048)


if __name__ == '__main__':
    unittest.main()
