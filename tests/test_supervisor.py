"""Provided-fact routing fixtures; no live Runtime or ownership discovery."""

from dataclasses import replace
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from yohaku import doctor
from yohaku.cli import _failure_guidance, main
from yohaku.supervisor import (AdapterRegistration, OBSERVER, TRIGGER, SessionProfile,
                               SupervisorError, YohakuSupervisor)


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.supervisor = YohakuSupervisor()
        self.session = SessionProfile('codex', 'thread-1', 'codex', 'fixture: explicit owner')
        self.supervisor.register_session(self.session)
        self.fixtures = []

    def register(self, name, roles=(TRIGGER, OBSERVER), *, session=None):
        session = session or self.session
        snapshot = SimpleNamespace(thread_id=session.provider_session_id,
                                   checkpoint=SimpleNamespace(checkpoint_id='checkpoint-1'))
        native = SimpleNamespace(session_id=session.provider_session_id)
        transition = Mock(return_value=name)
        registration = AdapterRegistration(name, session, frozenset(roles),
            lambda: (native.session_id,), lambda: snapshot,
            transition if TRIGGER in roles else None)
        self.supervisor.register_adapter(registration)
        self.fixtures.append((registration, snapshot, native, transition))
        return registration, snapshot, native, transition

    def refused(self, code, callable_, *args, **kwargs):
        with self.assertRaises(SupervisorError) as caught:
            callable_(*args, **kwargs)
        self.assertEqual(str(caught.exception), code)

    def test_one_trigger_preserves_call_arguments_and_result(self):
        registration, _, _, transition = self.register('codex')
        self.assertIs(self.supervisor.resolve(self.session), registration)
        lease, read_current = object(), Mock()
        self.assertEqual(self.supervisor.request_transition(self.session, lease, read_current,
                         requester='codex', completion_timeout=2), 'codex')
        transition.assert_called_once_with(lease, read_current, completion_timeout=2)
        read_current.assert_not_called()

    def test_meta_owner_suppresses_child_claim_without_precedence(self):
        session = replace(self.session, trigger_authority='meta')
        supervisor = YohakuSupervisor()
        self.supervisor, self.session = supervisor, session
        supervisor.register_session(session)
        _, _, _, child = self.register('codex')
        _, _, _, meta = self.register('meta')
        self.assertEqual([r.name for r in supervisor.observers(session)], ['codex', 'meta'])
        self.refused('SUPERVISOR_NOT_TRIGGER', supervisor.request_transition, session, requester='codex')
        self.assertEqual(supervisor.request_transition(session, requester='meta'), 'meta')
        child.assert_not_called()
        meta.assert_called_once()

    def test_auxiliary_meta_observer_leaves_dsh_in_authority(self):
        session = SessionProfile('dsh', 'native-session', 'dsh', 'fixture: terminal host')
        self.supervisor.register_session(session)
        _, _, _, meta = self.register('meta', (OBSERVER,), session=session)
        _, _, _, dsh = self.register('dsh', session=session)
        self.assertEqual([r.name for r in self.supervisor.observers(session)], ['dsh', 'meta'])
        self.refused('SUPERVISOR_NOT_TRIGGER', self.supervisor.request_transition, session, requester='meta')
        self.assertEqual(self.supervisor.request_transition(session, requester='dsh'), 'dsh')
        meta.assert_not_called()
        dsh.assert_called_once()

    def test_zero_observers_allowed(self):
        self.register('codex', (TRIGGER,))
        self.assertEqual(self.supervisor.observers(self.session), ())
        self.assertEqual(self.supervisor.request_transition(self.session, requester='codex'), 'codex')

    def test_observer_only_refuses_transition(self):
        self.register('codex', (OBSERVER,))
        self.refused('SUPERVISOR_NO_TRIGGER', self.supervisor.request_transition,
                     self.session, requester='codex')

    def test_no_registered_trigger_refuses(self):
        self.refused('SUPERVISOR_NO_TRIGGER', self.supervisor.resolve, self.session)

    def test_conflicting_trigger_claims_without_facts_refuse(self):
        session = SessionProfile('codex', 'unknown-owner')
        self.supervisor.register_session(session)
        for name in ('meta', 'codex'):
            self.register(name, session=session)
        self.refused('SUPERVISOR_MULTIPLE_TRIGGERS', self.supervisor.request_transition,
                     session, requester='codex')
        for _, _, _, transition in self.fixtures:
            transition.assert_not_called()

    def test_single_claim_with_unknown_or_incomplete_ownership_refuses(self):
        for authority, source in ((None, None), ('codex', None), (None, 'fixture')):
            with self.subTest(authority=authority, source=source):
                session = SessionProfile('codex', str((authority, source)), authority, source)
                self.supervisor.register_session(session)
                self.register('codex', session=session)
                self.refused('SUPERVISOR_AMBIGUOUS_OWNERSHIP', self.supervisor.resolve, session)

    def test_authority_fact_cannot_promote_observer_or_absent_adapter(self):
        self.register('codex', (OBSERVER,))
        self.register('meta')
        self.refused('SUPERVISOR_NO_TRIGGER', self.supervisor.resolve, self.session)
        missing = SessionProfile('codex', 'missing-owner', 'absent', 'fixture: explicit owner')
        self.supervisor.register_session(missing)
        self.register('codex', session=missing)
        self.refused('SUPERVISOR_NO_TRIGGER', self.supervisor.resolve, missing)

    def test_foreign_session_registration_and_request_refuse(self):
        self.register('codex')
        self.refused('SUPERVISOR_FOREIGN_SESSION', self.supervisor.resolve,
                     replace(self.session, provider_session_id='foreign'))
        self.refused('SUPERVISOR_FOREIGN_SESSION', self.supervisor.resolve,
                     replace(self.session, harness='dsh'))
        self.refused('SUPERVISOR_FOREIGN_SESSION', self.supervisor.request_transition,
                     self.session, requester='unregistered')
        wrong = AdapterRegistration('meta', self.session, frozenset({OBSERVER}),
            lambda: ('foreign',), lambda: SimpleNamespace(thread_id='thread-1'))
        self.refused('SUPERVISOR_FOREIGN_SESSION', self.supervisor.register_adapter, wrong)

    def test_native_or_core_identity_drift_stops_before_dispatch(self):
        _, snapshot, native, transition = self.register('codex')
        native.session_id = 'foreign'
        self.refused('SUPERVISOR_FOREIGN_SESSION', self.supervisor.request_transition,
                     self.session, requester='codex')
        native.session_id = 'thread-1'
        snapshot.thread_id = 'foreign'
        self.refused('SUPERVISOR_FOREIGN_SESSION', self.supervisor.resolve, self.session)
        transition.assert_not_called()

    def test_observer_identity_drift_also_blocks_resolution(self):
        self.register('codex')
        _, _, native, _ = self.register('meta', (OBSERVER,))
        native.session_id = 'foreign'
        self.refused('SUPERVISOR_FOREIGN_SESSION', self.supervisor.resolve, self.session)

    def test_unavailable_native_identity_fails_closed(self):
        identities = Mock(return_value=('thread-1',))
        registration = AdapterRegistration('codex', self.session, frozenset({TRIGGER}), identities,
            lambda: SimpleNamespace(thread_id='thread-1'), Mock())
        self.supervisor.register_adapter(registration)
        identities.side_effect = OSError('SECRET_IDENTITY_ERROR')
        self.refused('SUPERVISOR_FOREIGN_SESSION', self.supervisor.resolve, self.session)

    def test_conflicting_facts_and_duplicate_registration_refuse(self):
        self.refused('SUPERVISOR_AMBIGUOUS_OWNERSHIP', self.supervisor.register_session,
                     replace(self.session, trigger_authority='meta'))
        self.register('codex')
        self.refused('SUPERVISOR_AMBIGUOUS_OWNERSHIP', self.register, 'codex')
        self.refused('SUPERVISOR_AMBIGUOUS_OWNERSHIP', self.supervisor.resolve,
                     replace(self.session, ownership_source='different source'))

    def test_same_checkpoint_duplicate_after_return_is_not_dispatched(self):
        _, _, _, transition = self.register('codex')
        self.supervisor.request_transition(self.session, requester='codex')
        self.refused('SUPERVISOR_DUPLICATE_REQUEST', self.supervisor.request_transition,
                     self.session, requester='codex')
        transition.assert_called_once()

    def test_reentrant_request_is_rejected_before_dispatch(self):
        _, _, _, transition = self.register('codex')
        def dispatch():
            self.refused('SUPERVISOR_DUPLICATE_REQUEST', self.supervisor.request_transition,
                         self.session, requester='codex')
            self.refused('SUPERVISOR_NOT_TRIGGER', self.supervisor.request_transition,
                         self.session, requester='meta')
        self.register('meta', (OBSERVER,))
        transition.side_effect = dispatch
        self.supervisor.request_transition(self.session, requester='codex')
        transition.assert_called_once()

    def test_exception_does_not_allow_blind_retry(self):
        _, _, _, transition = self.register('codex')
        transition.side_effect = OSError('fixture: uncertain transport')
        with self.assertRaises(OSError):
            self.supervisor.request_transition(self.session, requester='codex')
        self.refused('SUPERVISOR_DUPLICATE_REQUEST', self.supervisor.request_transition,
                     self.session, requester='codex')
        transition.assert_called_once()

    def test_fresh_checkpoint_is_delegated_to_existing_adapter_checks(self):
        _, snapshot, _, transition = self.register('codex')
        self.supervisor.request_transition(self.session, requester='codex')
        snapshot.checkpoint = SimpleNamespace(checkpoint_id='checkpoint-2')
        self.supervisor.request_transition(self.session, requester='codex')
        self.assertEqual(transition.call_count, 2)

    def test_two_threads_in_same_harness_route_independently(self):
        self.register('codex')
        second = replace(self.session, provider_session_id='thread-2')
        self.supervisor.register_session(second)
        self.register('codex', session=second)
        for session in self.supervisor.sessions:
            self.supervisor.request_transition(session, requester='codex')
        for _, _, _, transition in self.fixtures:
            transition.assert_called_once()

    def test_resolution_order_is_deterministic_without_dispatch(self):
        self.register('z-observer', (OBSERVER,))
        self.register('codex')
        self.register('a-observer', (OBSERVER,))
        for _ in range(2):
            self.assertEqual(self.supervisor.resolve(self.session).name, 'codex')
            self.assertEqual([r.name for r in self.supervisor.observers(self.session)],
                             ['a-observer', 'codex', 'z-observer'])
        for _, _, _, transition in self.fixtures:
            transition.assert_not_called()

    def test_fresh_supervisor_has_no_restored_registry(self):
        self.register('codex')
        fresh = YohakuSupervisor()
        self.assertEqual(fresh.sessions, ())
        self.refused('SUPERVISOR_FOREIGN_SESSION', fresh.resolve, self.session)

    def test_failure_guidance_has_reason_safety_and_next_action(self):
        for code in ('NO_TRIGGER', 'MULTIPLE_TRIGGERS', 'AMBIGUOUS_OWNERSHIP',
                     'FOREIGN_SESSION', 'NOT_TRIGGER', 'DUPLICATE_REQUEST'):
            guidance = _failure_guidance('SUPERVISOR_' + code)
            for field in ('Reason:', 'Safety action:', 'Next action:'):
                self.assertIn(field, guidance)
        self.assertIn('No transition was started.', _failure_guidance('SUPERVISOR_NO_TRIGGER'))
        self.assertIn('stopped before dispatch.', _failure_guidance('SUPERVISOR_MULTIPLE_TRIGGERS'))

    def test_cli_failure_retains_routing_code_and_safe_guidance(self):
        for code in ('NO_TRIGGER', 'MULTIPLE_TRIGGERS', 'AMBIGUOUS_OWNERSHIP',
                     'FOREIGN_SESSION', 'NOT_TRIGGER', 'DUPLICATE_REQUEST'):
            reason = 'SUPERVISOR_' + code
            with self.subTest(reason=reason), patch('yohaku.cli.op.load'), \
                    patch('yohaku.cli.op.preflight', side_effect=SupervisorError(reason)), \
                    patch('builtins.print') as printer:
                self.assertEqual(main(['preflight', '--config', '/fixture/config']), 2)
                result = json.loads(printer.call_args.args[0])
            self.assertEqual(result['error'], reason)
            self.assertFalse(result['transition_ready'])
            self.assertFalse(result['transition_available'])
            self.assertEqual(result['guidance'], _failure_guidance(reason))

    def test_unknown_builtin_or_wrong_instance_cannot_register(self):
        self.refused('SUPERVISOR_FOREIGN_SESSION', self.supervisor.register_builtin,
                     'orca', object())
        self.refused('SUPERVISOR_FOREIGN_SESSION', self.supervisor.register_builtin,
                     'codex', object())

    def test_doctor_displays_supplied_facts_without_transition_calls(self):
        self.register('codex')
        with patch('yohaku.doctor.shutil.which', return_value=None):
            output = doctor.render(supervisor=self.supervisor)
        self.assertIn('Harness: codex', output)
        self.assertIn('Trigger authority: codex', output)
        self.assertIn('Observers: codex', output)
        self.assertIn('restart recovery: NOT_SUPPORTED', output)
        self.assertNotIn('thread-1', output)
        for _, _, _, transition in self.fixtures:
            transition.assert_not_called()

    def test_doctor_reports_refused_routing_without_dispatch(self):
        self.register('codex', (OBSERVER,))
        with patch('yohaku.doctor.shutil.which', return_value=None):
            output = doctor.render(supervisor=self.supervisor)
        self.assertIn('Trigger authority: unresolved', output)
        self.assertIn('No transition was started.', output)
        self.assertIn('Warnings: 1', output)

    def test_doctor_fallback_and_embedding_cli(self):
        self.register('codex')
        with patch('yohaku.doctor.shutil.which', return_value=None):
            self.assertEqual(doctor.render(), doctor.render(supervisor=None))
            self.assertNotIn('Supervisor sessions', doctor.render(supervisor=None))
            with patch('builtins.print') as printer:
                self.assertEqual(main(['doctor'], supervisor=self.supervisor), 0)
            self.assertIn('Trigger authority: codex', printer.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
