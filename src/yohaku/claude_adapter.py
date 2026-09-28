"""Bounded C-CLI owner adapter; no launcher, SDK, resume or restart support.

The host supplies a fresh dedicated SessionStore and serialized transport.
Checkpoint and metadata files are reused without changing the Codex codec.
All Runtime Hook events in the dispatch window must reach the adapter, including
unexpected, duplicate and failed ones. The host must close/drain that window.
"""

from dataclasses import asdict

from .claude import (ClaudeCLIProfile, ClaudeHookObservation, ClaudeManualBinding,
                     ClaudeManualCompletion, ClaudeManualCompletionPolicy)
from .controller import Controller, TransitionError
from .model import BoundaryVerification
from .persistence import _sync_directory
from .recovery import CurrentContext


class ClaudeCLIAdapter:
    def __init__(self, store, *, profile, startup, exclusive_fresh_session):
        if (profile != ClaudeCLIProfile() or exclusive_fresh_session is not True
                or not isinstance(startup, ClaudeHookObservation)
                or startup.event != "SessionStart" or startup.trigger != "startup"
                or startup.session_id != store.thread_id
                or startup.session_id in ("", "UNKNOWN")
                or not startup.attachment_id or not startup.evidence_ref
                or startup.request_id != "" or type(startup.generation) is not int
                or startup.generation != 0 or type(startup.seq) is not int or startup.seq != 1
                or startup.hook_ok is not True
                or store.latest is not None or tuple(store.checkpoints.iterdir())
                or tuple(store.journal.iterdir())):
            raise TransitionError("C-CLI needs the pinned, fresh exclusive session and store")
        store._ready()
        self.store, self.profile, self.startup = store, profile, startup
        self.core = Controller(store.thread_id, completion_policy=ClaudeManualCompletionPolicy())
        self.records = store.path / "claude-cli-events"
        self.records.mkdir(mode=0o700, exist_ok=False)
        _sync_directory(store.path)
        self.record_seq = 0
        self.stopped = False
        self.attempted = False
        self._record("attached", startup=asdict(startup), profile=asdict(profile))

    def _record(self, kind, **data):
        self.record_seq += 1
        path = self.records / f"{self.record_seq:06d}.json"
        self.store._write(path, dict(kind=kind, **data))
        return str(path)

    def _ready(self):
        self.store._ready()
        if self.stopped:
            raise TransitionError("C-CLI owner stopped; no retry or restart")

    def checkpoint(self, *, boundary_id, observe, evidence_ref, foreground_idle):
        """Host attests idle foreground and task boundary, not a global barrier."""
        self._ready()
        if foreground_idle is not True or not evidence_ref:
            raise TransitionError("observed idle foreground and boundary evidence required")
        current = observe()
        if not isinstance(current, CurrentContext):
            raise TransitionError("trusted task observation required")
        self.core.update_revisions(workspace=current.workspace)
        r = self.core.snapshot.revisions
        if (current.intent_revision, current.execution_revision) != (r.intent_revision, r.execution_revision):
            raise TransitionError("task and Core revisions disagree")
        try:
            self.core.propose_boundary(boundary_id)
            self.core.arm_barrier()
            self.core.begin_quiescence_check()
            self.core.observe_quiescence(relevant_work_remaining=False)
            self.core.capture_workspace(current.workspace)
            self.core.verify_boundary(BoundaryVerification(r.intent_revision, r.execution_revision,
                current.workspace, "implementation_complete", "not_run", evidence_ref))
            cp = self.store.commit_checkpoint(self.core.prepare_checkpoint())
            if observe() != current or self.store.read_checkpoint(cp.checkpoint_id) != cp:
                raise TransitionError("checkpoint observation changed")
            self.core.checkpoint_committed(cp.checkpoint_id, commit_evidence=cp.commit_evidence)
            self._record("checkpoint_committed", checkpoint_id=cp.checkpoint_id)
            return cp
        except BaseException:
            self.stopped = True
            self.core.fail("C-CLI checkpoint uncertain")
            raise

    def compact(self, *, observe, dispatch, now, request_seq, ttl=30):
        """Dispatch '/compact' once; callback returns the closed observation window.

        dispatch(command, binding) -> ClaudeManualCompletion. The host assigns a
        collector sequence before dispatch, retains actual native session IDs and
        attaches local request/attachment/generation to observations at capture.
        Returning a result/ACK with no Hooks is insufficient. No provider call is
        made by the library itself. Exceptions stop this attachment permanently.
        """
        self._ready()
        if self.attempted or type(request_seq) is not int or request_seq <= self.startup.seq:
            raise TransitionError("one fresh manual request and collector sequence required")
        lease = self.core.authorize_rollover(now=now(), ttl=ttl)
        current = observe()
        request = self.core.request_rollover(lease, now=now(), intent_revision=current.intent_revision,
            execution_revision=current.execution_revision, workspace=current.workspace)
        self.attempted = True
        try:
            binding = ClaudeManualBinding(request, self.startup.attachment_id, request.thread_id,
                self.startup.seq, request_seq, self.profile, True)
            self.core.bind_completion(binding)
            self._record("compact_requested", binding=asdict(binding), command="/compact")
            proof = dispatch("/compact", binding)
            if not isinstance(proof, ClaudeManualCompletion):
                raise TransitionError("missing closed C-CLI observation window")
            self._record("completion_window", proof=asdict(proof))
            if not self.core.observe_completion(proof):
                raise TransitionError("uncorrelated or incomplete C-CLI completion proof")
            return self.core.snapshot
        except BaseException:
            self.stopped = True
            self.core.fail("C-CLI dispatch or completion evidence uncertain")
            raise

    def require_work(self):
        self._ready()
        self.core.require_work()
