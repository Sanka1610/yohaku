"""Internal, process-local routing of supplied native-session ownership facts.

The embedding host serializes registration, observation and dispatch. This
module neither discovers owners nor grants Core authority or interprets proof.
"""

from dataclasses import dataclass
from typing import Callable

from .companion import CompanionController
from .dsh_adapter import DshAdapter
from .hermes_adapter import HermesCLIAdapter
from .opencode_adapter import OpenCodeAdapter


TRIGGER = 'TRIGGER'
OBSERVER = 'OBSERVER'


class SupervisorError(RuntimeError):
    """A routing refusal before entering the selected transition method."""


def failure_guidance(code):
    messages = {
        'SUPERVISOR_NO_TRIGGER': (
            'No transition authority is available for this session.',
            'No transition was started.',
            'Provide a session-matched trigger registration and explicit ownership facts.'),
        'SUPERVISOR_MULTIPLE_TRIGGERS': (
            'Multiple adapters claim transition authority for the same session.',
            'Yohaku stopped before dispatch.',
            'Resolve the conflicting claims with session-specific ownership facts.'),
        'SUPERVISOR_AMBIGUOUS_OWNERSHIP': (
            'Session ownership could not be determined safely.',
            'No transition was started.',
            'Confirm the native session and supply its trigger authority and ownership source.'),
        'SUPERVISOR_FOREIGN_SESSION': (
            'The adapter does not match the provider-native session.',
            'Yohaku stopped before dispatch.',
            'Check the harness and native session identity against the registered adapter.'),
        'SUPERVISOR_NOT_TRIGGER': (
            'The requesting adapter is not the selected transition authority.',
            'No transition was started by this request.',
            'Route the request through the selected trigger; keep observers read-only.'),
        'SUPERVISOR_ORCA_DIRECT_TRIGGER': (
            'This Codex session is owned by Orca structured chat. Trigger authority: Orca.',
            'Direct Codex transition was not started.',
            'Request the transition through the Orca adapter in the Supervisor.'),
        'SUPERVISOR_DUPLICATE_REQUEST': (
            'A transition method was already entered for this session and checkpoint.',
            'Yohaku stopped this request before dispatch and did not retry.',
            'Preserve state and reconcile the existing operation; obtain a fresh Core checkpoint before a new transition.'),
    }
    fields = messages.get(code)
    if fields is None:
        return None
    return '\n'.join(f'{label}: {value}' for label, value in
                     zip(('Reason', 'Safety action', 'Next action'), fields))


@dataclass(frozen=True)
class SessionProfile:
    harness: str
    provider_session_id: str
    trigger_authority: str | None = None
    ownership_source: str | None = None

    def __post_init__(self):
        if not self.harness or not self.provider_session_id:
            raise SupervisorError('SUPERVISOR_FOREIGN_SESSION')


@dataclass(frozen=True)
class AdapterRegistration:
    name: str
    session: SessionProfile
    roles: frozenset[str]
    read_session_ids: Callable
    read_snapshot: Callable
    transition: Callable | None = None

    def __post_init__(self):
        object.__setattr__(self, 'roles', frozenset(self.roles))
        if (not self.name or not self.roles or not self.roles <= {TRIGGER, OBSERVER}
                or (TRIGGER in self.roles and not callable(self.transition))):
            raise ValueError('session roles and a transition callable for triggers required')


class YohakuSupervisor:
    def __init__(self):
        self._sessions = {}
        self._adapters = {}
        self._entered = set()
        self._active = set()

    @staticmethod
    def _key(session):
        # These are native values, not a new persistent or universal identifier.
        return session.harness, session.provider_session_id

    @property
    def sessions(self):
        return tuple(self._sessions[key] for key in sorted(self._sessions))

    def register_session(self, session):
        key = self._key(session)
        if key in self._sessions and self._sessions[key] != session:
            raise SupervisorError('SUPERVISOR_AMBIGUOUS_OWNERSHIP')
        self._sessions[key] = session
        self._adapters.setdefault(key, {})

    def _session(self, session):
        known = self._sessions.get(self._key(session))
        if known is None:
            raise SupervisorError('SUPERVISOR_FOREIGN_SESSION')
        if known != session:
            raise SupervisorError('SUPERVISOR_AMBIGUOUS_OWNERSHIP')
        return known

    @staticmethod
    def _check_identity(registration):
        try:
            identities = registration.read_session_ids()
            snapshot = registration.read_snapshot()
            valid = (bool(identities) and all(identity == registration.session.provider_session_id
                                            for identity in identities)
                     and snapshot.thread_id == registration.session.provider_session_id)
        except Exception:
            valid = False
        if not valid:
            raise SupervisorError('SUPERVISOR_FOREIGN_SESSION')
        return snapshot

    def register_adapter(self, registration):
        self._session(registration.session)
        self._check_identity(registration)
        entries = self._adapters[self._key(registration.session)]
        if registration.name in entries:
            raise SupervisorError('SUPERVISOR_AMBIGUOUS_OWNERSHIP')
        entries[registration.name] = registration
        return registration

    def register_builtin(self, harness, adapter, *, session=None, roles=(TRIGGER, OBSERVER)):
        """Register an already attached built-in; omission of session declares standalone use."""
        types = {'codex': (CompanionController, 'request_compact'),
                 'hermes': (HermesCLIAdapter, 'compress'),
                 'dsh': (DshAdapter, 'compact'),
                 'opencode': (OpenCodeAdapter, 'compact')}
        if harness not in types or not isinstance(adapter, types[harness][0]):
            raise SupervisorError('SUPERVISOR_FOREIGN_SESSION')
        read_snapshot = (lambda: adapter.snapshot) if harness == 'codex' else (lambda: adapter.core.snapshot)
        def read_session_ids():
            ids = (adapter.store.thread_id,)
            if harness in ('hermes', 'dsh'):
                ids += (adapter.host.session_id,)
            return ids
        if session is None:
            session = SessionProfile(harness, read_snapshot().thread_id,
                                     harness, 'embedding host: standalone registration')
            self.register_session(session)
        if session.harness != harness:
            raise SupervisorError('SUPERVISOR_FOREIGN_SESSION')
        roles = frozenset(roles)
        transition = getattr(adapter, types[harness][1]) if TRIGGER in roles else None
        return self.register_adapter(AdapterRegistration(harness, session, roles,
            read_session_ids, read_snapshot, transition))

    def observers(self, session):
        self._session(session)
        entries = self._adapters[self._key(session)]
        observers = tuple(entries[name] for name in sorted(entries) if OBSERVER in entries[name].roles)
        for registration in observers:
            self._check_identity(registration)
        return observers

    def resolve(self, session):
        session = self._session(session)
        entries = self._adapters[self._key(session)]
        for name in sorted(entries):
            self._check_identity(entries[name])
        triggers = tuple(entries[name] for name in sorted(entries) if TRIGGER in entries[name].roles)
        if not triggers:
            raise SupervisorError('SUPERVISOR_NO_TRIGGER')
        if not session.trigger_authority or not session.ownership_source:
            if len(triggers) > 1:
                raise SupervisorError('SUPERVISOR_MULTIPLE_TRIGGERS')
            raise SupervisorError('SUPERVISOR_AMBIGUOUS_OWNERSHIP')
        selected = entries.get(session.trigger_authority)
        if selected is None or TRIGGER not in selected.roles:
            raise SupervisorError('SUPERVISOR_NO_TRIGGER')
        return selected

    def request_transition(self, session, *args, requester, **kwargs):
        """Enter only the selected method, preserving its arguments and Core checks."""
        selected = self.resolve(session)
        if requester not in self._adapters[self._key(session)]:
            raise SupervisorError('SUPERVISOR_FOREIGN_SESSION')
        if requester != selected.name:
            if (session.harness == 'codex' and selected.name == 'orca'
                    and session.ownership_source == 'orca-structured-session' and requester == 'codex'):
                raise SupervisorError('SUPERVISOR_ORCA_DIRECT_TRIGGER')
            raise SupervisorError('SUPERVISOR_NOT_TRIGGER')
        snapshot = self._check_identity(selected)
        key = self._key(session)
        # The existing checkpoint scopes duplicate suppression. No new lease is
        # granted; all freshness, authorization and persistence checks stay in Core/adapter.
        checkpoint_id = snapshot.checkpoint.checkpoint_id if snapshot.checkpoint else None
        attempt = key, checkpoint_id
        if key in self._active or attempt in self._entered:
            raise SupervisorError('SUPERVISOR_DUPLICATE_REQUEST')
        self._entered.add(attempt)
        self._active.add(key)
        try:
            return selected.transition(*args, **kwargs)
        finally:
            # Retain the attempted checkpoint even on exceptions; never infer non-execution.
            self._active.remove(key)
