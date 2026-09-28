"""Host-bound receipt challenge: negative evidence must never grant recovery."""
from dataclasses import replace
import unittest
from unittest.mock import patch

import test_claude_recovery as legacy
from yohaku.claude_recovery import ClaudeCLINonceRecoveryAdapter
from yohaku.controller import TransitionError
from yohaku.model import State


class NonceReceiptTests(unittest.TestCase):
    adapter_type = ClaudeCLINonceRecoveryAdapter
    setUp = legacy.ClaudeRecoveryTests.setUp
    observe = legacy.ClaudeRecoveryTests.observe
    event = legacy.ClaudeRecoveryTests.event
    pre = legacy.ClaudeRecoveryTests.pre
    post = legacy.ClaudeRecoveryTests.post
    fresh = legacy.ClaudeRecoveryTests.fresh
    action = legacy.ClaudeRecoveryTests.action
    terminal = legacy.ClaudeRecoveryTests.terminal
    proof = legacy.ClaudeRecoveryTests.proof

    def begin(self):
        original = self.a.begin_recovery
        def capture(*args, **kw):
            def instructions(fields):
                self.fields = fields
                return 'Echo this one-time challenge: ' + str(fields)
            kw['instructions'] = instructions
            return original(*args, **kw)
        with patch.object(self.a, 'begin_recovery', side_effect=capture):
            return legacy.ClaudeRecoveryTests.begin(self)

    def receipt(self):
        self.pre('receipt')
        result = self.a.acknowledge(self.fields)
        self.assertEqual(self.a.core.snapshot.state, State.HANDOFF_OFFERED)
        self.post(result, 'receipt')

    def rejected(self, action):
        with self.assertRaises(TransitionError):
            action()
        self.assertTrue(self.a.stopped)
        self.assertEqual(self.a.core.snapshot.state, State.RECOVERY_REQUIRED)
        self.assertIsNone(self.a.core.snapshot.receipt_evidence)
        self.assertEqual(self.effects, {'before': 1, 'after': 0, 'stale': 0})

    def test_only_nonce_is_exposed_and_independent_chain_verifies(self):
        self.begin()
        self.assertEqual(set(self.fields), {'nonce'})
        self.assertEqual(len(self.fields['nonce']), 22)
        self.assertIn(self.fields['nonce'], self.a.prompt)
        self.receipt(); self.fresh(); self.action(); self.terminal()
        self.assertEqual(self.a.verify_resume(observe=self.observe, assess=self.proof).state, State.RESUME_VERIFIED)

    def test_missing_stale_foreign_and_malformed_nonce_rejected(self):
        # Each failed owner is permanent; fresh owners are used by subtests.
        cases = [None, {}, {'nonce': 'old'}, {'nonce': '\u00e9'}, {'nonce': True},
                 {'nonce': 'x' * 22, 'session_id': 'session'}]
        for fields in cases:
            with self.subTest(fields=fields):
                case = NonceReceiptTests(); case.setUp()
                try:
                    case.begin(); case.pre('receipt')
                    case.rejected(lambda: case.a.acknowledge(fields))
                finally: case.doCleanups()

    def test_full_identity_echo_cannot_bypass_nonce_protocol(self):
        self.begin(); self.pre('receipt')
        self.rejected(lambda: self.a.acknowledge(self.a.receipt_fields()))

    def test_wrong_owner_challenge_rejected(self):
        self.begin(); foreign = dict(self.fields)
        other = NonceReceiptTests(); other.setUp()
        try:
            other.begin(); other.pre('receipt')
            self.assertNotEqual(foreign, other.fields)
            other.rejected(lambda: other.a.acknowledge(foreign))
        finally: other.doCleanups()

    def test_each_host_identity_mismatch_rejected(self):
        for key in ('handoff_id', 'checkpoint_id', 'checkpoint_hash', 'handoff_hash',
                    'request_id', 'session_id', 'attachment_id', 'generation',
                    'continuation_request_id', 'continuation_turn_id', 'logical_task_id'):
            with self.subTest(key=key):
                case = NonceReceiptTests(); case.setUp()
                try:
                    case.begin(); case.pre('receipt')
                    bad = {**case.a.receipt_fields(), key: 'foreign'}
                    with patch.object(case.a, 'receipt_fields', return_value=bad):
                        case.rejected(lambda: case.a.acknowledge(case.fields))
                finally: case.doCleanups()

    def test_wrong_session_attachment_request_generation_and_sequence_rejected(self):
        mutations = [dict(session_id='foreign'), dict(seq=15)]
        for field, value in [('attachment_id', 'other-owner'), ('thread_id', 'foreign'),
                             ('compact_request_id', 'old'), ('request_id', 'old'),
                             ('turn_id', 'old'), ('generation', 0), ('generation', True)]:
            mutations.append((field, value))
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                case = NonceReceiptTests(); case.setUp()
                try:
                    case.begin(); event = case.event()
                    if isinstance(mutation, tuple):
                        event['binding'] = replace(event['binding'], **{mutation[0]: mutation[1]})
                    else: event.update(mutation)
                    case.rejected(lambda: case.a.pre_tool(**event, tool_id='receipt', operation='receipt'))
                finally: case.doCleanups()

    def test_ack_without_native_admission_rejected(self):
        self.begin()
        self.rejected(lambda: self.a.acknowledge(self.fields))

    def test_duplicate_handler_rejected_before_post(self):
        self.begin(); self.pre('receipt'); self.a.acknowledge(self.fields)
        self.rejected(lambda: self.a.acknowledge(self.fields))

    def test_missing_post_never_grants_observation(self):
        self.begin(); self.pre('receipt'); self.a.acknowledge(self.fields)
        self.rejected(lambda: self.pre('observe'))

    def test_wrong_post_result_rejected(self):
        self.begin(); self.pre('receipt'); self.a.acknowledge(self.fields)
        self.rejected(lambda: self.post({'receipt': 'accepted'}, 'receipt'))

    def test_wrong_post_tool_rejected(self):
        self.begin(); self.pre('receipt'); result = self.a.acknowledge(self.fields)
        self.rejected(lambda: self.post(result, 'foreign'))

    def test_timeout_stopped_owner_cannot_ack(self):
        self.begin(); self.pre('receipt')
        self.a.stopped = True; self.a.core.fail('owner deadline expired')
        self.rejected(lambda: self.a.acknowledge(self.fields))

    def test_duplicate_completed_ack_stops_owner(self):
        self.begin(); self.receipt()
        with self.assertRaises(TransitionError): self.pre('receipt', 'second')
        self.assertEqual(self.a.core.snapshot.state, State.RECOVERY_REQUIRED)
        self.assertEqual(self.effects['after'], 0)

    def test_terminal_or_successful_effect_without_receipt_rejected(self):
        self.begin()
        self.rejected(self.terminal)

    def test_nonce_receipt_does_not_skip_fresh_token_or_assessment(self):
        self.begin(); self.receipt(); self.fresh(); self.pre('action')
        with self.assertRaises(TransitionError):
            self.a.perform_action({'fresh_read_id': 'stale'}, observe=self.observe,
                                  execute=lambda: self.fail('executed'))
        self.assertEqual(self.effects['after'], 0)


if __name__ == '__main__': unittest.main()
