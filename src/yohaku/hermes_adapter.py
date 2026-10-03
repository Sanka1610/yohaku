"""Pinned H-CLI-01 host adapter. One fresh owner, foreground work, one /compress.

The embedding host supplies the send gate, PluginContext hooks and trusted task
observers. This is not a runtime-wide barrier or a restartable Core journal.
Use a fresh dedicated SessionStore; never attach a regular Codex session store.
"""

from dataclasses import asdict
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .controller import Controller, TransitionError
from .hermes import (HERMES_SOURCE, HERMES_VERSION, HermesManualBinding,
                     HermesManualCompletion, HermesManualCompletionPolicy)
from .model import BoundaryVerification, ContinuationBinding, ResumeVerification, State
from .persistence import _read, _sync_directory
from .recovery import CurrentContext, HandoffDocument, ResumeProof


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def history_payload(messages):
    return [{k: m[k] for k in ('role', 'content', 'tool_calls', 'tool_call_id')
             if k in m and m[k] is not None} for m in messages]


class HermesCLIAdapter:
    def __init__(self, host, store, *, version, source_commit, exclusive_fresh_session,
                 tool_name, db_path):
        if (version != HERMES_VERSION or source_commit != HERMES_SOURCE
                or exclusive_fresh_session is not True or host.conversation_history
                or host.agent.context_compressor.compression_count != 0
                or host.agent.compression_enabled or store.thread_id != host.session_id
                or store.latest is not None or tuple(store.checkpoints.iterdir())
                or tuple(store.journal.iterdir()) or not tool_name):
            raise TransitionError('H-CLI-01 needs the pinned, fresh, exclusive host and store')
        store._ready()
        self.host, self.store, self.tool_name = host, store, tool_name
        self.db_path = Path(db_path).resolve()
        self.core = Controller(host.session_id, completion_policy=HermesManualCompletionPolicy())
        self.events = []
        self.records = store.path / 'hermes-events'
        self.records.mkdir(mode=0o700, exist_ok=False)
        _sync_directory(store.path)
        self.active, self.pending, self.tools = {}, {}, {}
        self.stopped = False
        self.foreground = False
        self.turn_id = None
        self.document = None
        self.prompt = None
        self.receipt_call = None
        self.fresh_read = None
        self.manual_requests = 0
        self._record('attached', version=version, source_commit=source_commit)

    def _record(self, kind, **data):
        event = dict(seq=len(self.events) + 1, kind=kind,
                     session_id=self.core.snapshot.thread_id, **data)
        try:
            path = self.records / f'{event["seq"]:06d}.json'
            self.store._write(path, event)
        except Exception:
            self.stopped = True
            self.core.fail('Hermes evidence write uncertain')
            raise
        self.events.append(event)
        return str(path)

    def _ready(self):
        self.store._ready()
        if self.stopped or self.host.session_id != self.core.snapshot.thread_id:
            raise TransitionError('Hermes owner stopped or session changed')

    def _stop(self, reason):
        self.stopped = True
        self.core.fail(reason)
        raise TransitionError(reason)

    def _idle(self):
        self._ready()
        if self.foreground or self.active or self.pending:
            raise TransitionError('foreground work or unincorporated results remain')

    def chat(self, prompt):
        """Owner-only native foreground chat; work hooks must already be installed."""
        self._idle()
        if self.document is None:
            self.core.require_work()
        elif prompt != self.prompt or self.core.snapshot.state != State.ROLLOVER_OBSERVED:
            raise TransitionError('only the claimed handoff may start the continuation')
        self.foreground = True
        self.turn_id = None
        self.terminal = False
        try:
            self.host.chat(prompt)
            self._ready()
            if self.active or self.pending or not self.terminal:
                self._stop('foreground turn lacks terminal/result incorporation evidence')
        except BaseException:
            if not self.stopped:
                self.stopped = True
                self.core.fail('native foreground dispatch uncertain')
            raise
        finally:
            self.foreground = False

    def observe_terminal(self, *, turn_id, session_id, failed, interrupted):
        """Called by the trusted host after native run_conversation returns."""
        self._ready()
        if (not self.foreground or turn_id != self.turn_id
                or session_id != self.core.snapshot.thread_id
                or failed is not False or interrupted is not False):
            self._stop('native turn did not complete successfully')
        self.terminal = True
        self._record('turn_completed', turn_id=turn_id)

    def observe_request(self, body):
        """Inspect actual Responses wire input at the embedding host's send gate.

        Never log payloads. Pending means result present in an outgoing request,
        not that the model understood it. The send gate must abort on exceptions.
        """
        self._ready()
        if not self.foreground:
            return  # manual compressor has no foreground task result incorporation
        turn = self.host.agent._current_turn_id
        if not turn or (self.turn_id is not None and turn != self.turn_id):
            self._stop('missing or changed native foreground turn')
        self.turn_id = turn
        if self.document is not None and self.core.snapshot.handoff is None:
            inputs = body.get('input', [])
            texts = [m.get('content') for m in inputs if m.get('role') == 'user']
            def text(value):
                return value if isinstance(value, str) else ''.join(
                    part.get('text', '') for part in (value or []) if isinstance(part, dict))
            if not any(text(value) == self.prompt for value in texts):
                self._stop('handoff absent from native outgoing user input')
            self.core.offer_handoff(ContinuationBinding(self.core.snapshot.continuation_request_id,
                self.host.session_id, turn), recovered_context=self.handoff_text,
                handoff_id=self.document.handoff_id)
            self.injection = self._record('handoff_in_request', turn_id=turn,
                                         prompt_hash=digest(self.prompt))
        for item in body.get('input', []):
            cid = item.get('call_id')
            if item.get('type') != 'function_call_output' or cid not in self.pending:
                continue
            record = self.pending[cid]
            if (record['turn_id'] != turn or not isinstance(item.get('output'), str)
                    or digest(item['output']) != record['result_hash']):
                self._stop('result incorporation identity mismatch')
            record['incorporated'] = True
            self._record('result_in_request', call_id=cid, turn_id=turn,
                         result_hash=digest(item['output']))
            del self.pending[cid]
            if cid == self.receipt_call:
                proof = self._record('explicit_receipt', call_id=cid, turn_id=turn,
                                     receipt=self.receipt_fields())
                self.core.receive_handoff(self.core.snapshot.handoff,
                    injection_evidence=self.injection, receipt_evidence=proof)

    def pre_tool(self, **kw):
        self._ready()
        cid, turn = kw.get('tool_call_id'), kw.get('turn_id')
        if (not self.foreground or kw.get('session_id') != self.host.session_id
                or turn != self.turn_id or not cid or not kw.get('api_request_id')
                or cid in self.tools or self.active or self.pending
                or kw.get('tool_name') != self.tool_name):
            self._stop('tool outside the observed single foreground profile')
        record = dict(call_id=cid, turn_id=turn, api_request_id=kw['api_request_id'],
                      status='active', incorporated=False)
        self.active[cid] = self.tools[cid] = record
        self._record('tool_start', **record)

    def post_tool(self, **kw):
        self._ready()
        cid = kw.get('tool_call_id')
        if (cid not in self.active or kw.get('session_id') != self.host.session_id
                or kw.get('turn_id') != self.active[cid]['turn_id']
                or kw.get('api_request_id') != self.active[cid]['api_request_id']
                or kw.get('status') not in ('ok', 'blocked')):
            self._stop('tool completion missing or unsuccessful')
        record = self.active.pop(cid)
        record['status'] = kw['status']
        if not isinstance(kw.get('result'), str):
            self._stop('only text tool results are covered')
        record['result_hash'] = digest(kw['result'])
        if cid == self.receipt_call and record['status'] != 'ok':
            self._stop('receipt tool failed')
        self.pending[cid] = record
        self._record('tool_completed', **record)

    def require_tool(self):
        """Call at handler entry; native observer-hook exceptions may be swallowed."""
        self._ready()
        if not self.foreground or len(self.active) != 1:
            self._stop('handler lacks observed foreground admission')

    def checkpoint(self, *, boundary_id, observe, evidence_ref, archive_ids=()):
        self._idle()
        current = observe()
        if not isinstance(current, CurrentContext) or not evidence_ref:
            raise TransitionError('trusted current task observation required')
        self.core.update_revisions(workspace=current.workspace)
        r = self.core.snapshot.revisions
        if (current.intent_revision, current.execution_revision) != (r.intent_revision, r.execution_revision):
            raise TransitionError('task and Core revisions disagree')
        self.core.propose_boundary(boundary_id)
        self.core.arm_barrier()  # Core sequencing only; no runtime-wide freeze claim.
        self.core.begin_quiescence_check()
        self.core.observe_quiescence(relevant_work_remaining=False)
        self.core.capture_workspace(current.workspace)
        self.core.verify_boundary(BoundaryVerification(r.intent_revision, r.execution_revision,
            current.workspace, 'implementation_complete', 'passed', evidence_ref))
        cp = self.store.commit_checkpoint(self.core.prepare_checkpoint(), archive_ids=archive_ids)
        if observe() != current or self.store.read_checkpoint(cp.checkpoint_id) != cp:
            self._stop('checkpoint current state changed')
        self.core.checkpoint_committed(cp.checkpoint_id, commit_evidence=cp.commit_evidence)
        self.current = current
        self.checkpoint_hash = _read(self.store.checkpoints / f'{cp.checkpoint_id}.json')['sha256']
        self._record('checkpoint_committed', checkpoint_id=cp.checkpoint_id,
                     checkpoint_hash=self.checkpoint_hash)
        return cp

    def compress(self, *, observe, now, ttl=30):
        self._idle()
        if self.manual_requests:
            raise TransitionError('H-CLI-01 allows one manual request')
        lease = self.core.authorize_rollover(now=now(), ttl=ttl)
        current = observe()
        request = self.core.request_rollover(lease, now=now(), intent_revision=current.intent_revision,
            execution_revision=current.execution_revision, workspace=current.workspace)
        self.manual_requests = 1
        try:
            self._record('compress_requested', request=asdict(request))
            binding = HermesManualBinding(request, self.host.session_id, len(self.events),
                                          HERMES_VERSION, HERMES_SOURCE, True)
            self.core.bind_completion(binding)
            before = digest(history_payload(self.host.conversation_history))
            self.host._manual_compress('/compress')
            from hermes_state import SessionDB
            reader = SessionDB(db_path=self.db_path, read_only=True)
            try:
                messages = reader.get_messages_as_conversation(self.host.session_id)
            finally:
                reader.close()
            with closing(sqlite3.connect(self.db_path.as_uri() + '?mode=ro', uri=True)) as connection:
                archived = connection.execute('select count(*) from messages where session_id=? and active=0',
                                              (self.host.session_id,)).fetchone()[0]
            host, db = history_payload(self.host.conversation_history), history_payload(messages)
            fields = dict(request_id=request.request_id, readback_seq=len(self.events) + 1,
                session_before=binding.session_id, session_after=self.host.session_id,
                compressor_count=self.host.agent.context_compressor.compression_count,
                manual_requests=self.manual_requests, readback_count=1,
                host_changed=digest(host) != before, independent_db_read=True,
                db_payload_matches_host=host == db, host_history_hash=digest(host),
                db_history_hash=digest(db), host_history_count=len(host),
                db_message_count=len(db), archived_rows=archived)
            ref = self._record('host_storage_readback', **fields)
            if not self.core.observe_completion(HermesManualCompletion(binding, ref, **fields)):
                self._stop('Hermes completion policy rejected readback')
            self._record('rollover_observed', request_id=request.request_id)
        except BaseException:
            self.stopped = True
            self.core.fail('manual compression or readback uncertain')
            raise
        return self.core.snapshot

    def receipt_fields(self):
        d = self.document
        return dict(handoff_id=d.handoff_id, checkpoint_id=d.request.checkpoint_id,
                    checkpoint_hash=self.checkpoint_hash, request_id=d.request.request_id,
                    session_id=d.request.thread_id, generation=d.request.rollover_generation)

    def continue_task(self, recovered, *, cwd, instructions):
        self._idle()
        s = self.core.snapshot
        if recovered.logical_task_id != self.current.logical_task_id:
            raise TransitionError('handoff task changed')
        if recovered.archive_ids != self.store.checkpoint_archive_ids(s.checkpoint.checkpoint_id):
            raise TransitionError('handoff archive references differ from checkpoint')
        permit = self.core.claim_continuation()
        self.document = HandoffDocument(uuid4().hex, s.request, s.checkpoint.revisions,
            s.checkpoint.workspace, str(Path(cwd).resolve()), recovered)
        self.store.commit_handoff(self.document)
        self.handoff_text = self.document.render(checkpoint=s.checkpoint)
        self.prompt = (self.handoff_text + '\n[Yohaku explicit receipt]\n'
            + json.dumps(self.receipt_fields(), sort_keys=True)
            + '\nFirst call the receipt operation with every field above exactly. '
            'Then read fresh task state and reconcile it before acting.\n' + instructions)
        self._record('continuation_claimed', continuation_request_id=permit,
                     handoff_id=self.document.handoff_id)
        self.chat(self.prompt)
        if self.core.snapshot.receipt_evidence is None:
            self.core.recovery_required('explicit receipt missing; behavioral success is insufficient')

    def acknowledge(self, fields):
        """Called by the actual receipt tool handler, never by the controller."""
        self._ready()
        if (self.core.snapshot.state != State.HANDOFF_OFFERED or self.receipt_call
                or len(self.active) != 1 or fields != self.receipt_fields()
                or type(fields.get('generation')) is not int):
            self._stop('explicit receipt missing or mismatched')
        self.receipt_call = next(iter(self.active))
        self._record('receipt_tool_validated', call_id=self.receipt_call, receipt=fields)
        return {'receipt': 'accepted'}

    def reconcile_fresh(self, observe):
        self._ready()
        if self.core.snapshot.state != State.HANDOFF_RECEIVED or len(self.active) != 1:
            raise TransitionError('fresh read needs explicit receipt and actual read tool')
        current = observe()
        if current.logical_task_id != self.document.recovered.logical_task_id:
            self._stop('fresh task identity changed')
        self.core.reconcile_resume_context(intent_revision=current.intent_revision,
            execution_revision=current.execution_revision, workspace=current.workspace)
        self.fresh_read = next(iter(self.active))
        self._record('fresh_state_reconciled', call_id=self.fresh_read, current=asdict(current))
        return current

    def require_action(self):
        self._ready()
        read = self.tools.get(self.fresh_read, {})
        if (self.core.snapshot.state != State.HANDOFF_RECEIVED
                or read.get('status') != 'ok' or not read.get('incorporated')):
            raise TransitionError('action needs incorporated fresh read after explicit receipt')

    def verify_resume(self, *, observe, assess):
        self._idle()
        self.require_action()
        before = observe()
        proof = assess(self.document, tuple(dict(r) for r in self.tools.values()))
        after = observe()
        turn = self.core.snapshot.handoff.continuation_turn_id
        successful = {cid for cid, r in self.tools.items()
                      if r['turn_id'] == turn and r['status'] == 'ok' and r['incorporated']}
        if (not isinstance(proof, ResumeProof) or before != after or proof.current != after
                or after.logical_task_id != self.document.recovered.logical_task_id
                or self.fresh_read not in proof.read_item_ids or not proof.action_item_ids
                or not set(proof.read_item_ids + proof.action_item_ids) <= successful):
            self._stop('resume task evidence missing or stale')
        self.core.reconcile_resume_context(intent_revision=after.intent_revision,
            execution_revision=after.execution_revision, workspace=after.workspace)
        self.core.verify_resume(ResumeVerification(self.document.handoff_id, turn,
            after.intent_revision, after.execution_revision, after.workspace, proof.evidence_ref,
            True, True, proof.unresolved_checked, proof.next_action_reevaluated,
            proof.completed_work_not_repeated, proof.historical_instructions_not_reexecuted,
            proof.same_task_continued))
        self._record('resume_verified', current=asdict(after))
        return self.core.snapshot
