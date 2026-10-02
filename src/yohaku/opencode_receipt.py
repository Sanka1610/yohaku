"""Owned OpenCode 2.0.21 unbound receipt and one late-bound text continuation.

The host attests the fixed builtin graph and exclusive lifecycle. Catalog and
source checks supplement that attestation; the catalog is not a hook-order API.
All gate decisions are serialized with the owner. No proof survives restart.
"""

import base64
from contextlib import closing
from dataclasses import asdict
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
import threading
import time
import urllib.parse
from uuid import uuid4

from .controller import Controller, TransitionError
from .codec import encode
from .model import ContinuationBinding, State
from .opencode import OpenCodeNativeCompletionPolicy
from .opencode_adapter import OpenCodeAdapter
from .recovery import CurrentContext, HandoffDocument


HOOK = Path(__file__).with_name("opencode_receipt_hook.mjs")
BUILTINS = frozenset(("opencode.agent", "opencode.provider.ollama",
    "opencode.provider.opencode", "opencode.config.provider",
    "opencode.config.compaction", "opencode.config.policy", "opencode.config.agent"))
PLUGIN_ID = "yohaku.opencode.receipt"


class OpenCodeReceiptCompletionPolicy(OpenCodeNativeCompletionPolicy):
    """R4-only offered native delivery; R3 completion validation is inherited."""
    delivery = None

    def permits_continuation(self, binding, continuation):
        return (self.valid_binding(binding) and self.delivery == continuation
                and continuation.thread_id == binding.session_id)


class OpenCodeReceiptHost:
    """Authenticated loopback bridge for the packaged terminal observer only."""
    def __init__(self, *, directory, plugin_path):
        self.directory = str(Path(directory).resolve())
        self.plugin_path = Path(plugin_path).resolve()
        self.token = secrets.token_urlsafe(32)
        self.epoch = None
        self.counter = 0
        self.adapter = None
        self.closed = False
        self.lock = threading.RLock()
        host = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                status, answer = 200, {"action": "deny"}
                try:
                    if self.headers.get("Authorization") != "Bearer " + host.token:
                        raise TransitionError("untrusted receipt observer")
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= 2_000_000:
                        raise TransitionError("receipt observation size invalid")
                    data = json.loads(self.rfile.read(size))
                    answer = host.call(self.path, data)
                except Exception:
                    # A lost/malformed host exchange never grants a release.
                    with host.lock:
                        if host.adapter is not None:
                            host.adapter._invalidate("receipt host exchange failed")
                    status = 409
                raw = json.dumps(answer).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                try:
                    self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError):
                    with host.lock:
                        if host.adapter is not None:
                            host.adapter._invalidate("receipt observer disconnected")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def options(self):
        # Put these credentials in private temporary config, never in evidence.
        return {"origin": self.origin, "token": self.token}

    def call(self, path, data):
        with self.lock:
            if self.closed:
                raise TransitionError("receipt host disposed")
            if path == "/hello":
                if self.epoch is not None or data["directory"] != self.directory:
                    raise TransitionError("receipt observer replaced/foreign")
                self.epoch = str(uuid4())
                return {"epoch": self.epoch}
            if self.adapter is None:
                raise TransitionError("receipt owner unavailable")
        # Observation waits without holding the owner lock.
        return self.adapter._hook(path, data)

    def close(self):
        with self.lock:
            self.closed = True
            if self.adapter is not None:
                self.adapter._invalidate("receipt host disposed", stop=False)
        self.server.shutdown()
        self.server.server_close()


class OpenCodeReceiptAdapter(OpenCodeAdapter):
    def __init__(self, store, *, receipt_host, known_terminal_graph,
                 observe_current, owner_alive, provider_request_url, **kwargs):
        # These are trusted embedding-host attestations, not discovery results.
        if known_terminal_graph is not True:
            raise TransitionError("known terminal hook graph is required")
        self.host = receipt_host
        self.provider_request_url = provider_request_url
        self.observe_current, self.owner_alive = observe_current, owner_alive
        self.receipt_policy = OpenCodeReceiptCompletionPolicy()
        self.document = None
        self.candidate = None
        self.deadline = None
        self.promoted = False
        self.observed = threading.Event()
        self.task_candidate = None
        self.task_observed = threading.Event()
        super().__init__(store, **kwargs)
        try:
            with self.host.lock:
                if (self.host.adapter is not None or self.host.closed
                        or self.host.directory != self.directory or not self.owner_alive()):
                    raise TransitionError("receipt needs a single live owned host")
                self._graph()
                self.host.adapter = self
        except Exception:
            super().close()
            raise

    def _controller(self, session_id):
        return Controller(session_id, completion_policy=self.receipt_policy)

    def _graph(self):
        if self.host.plugin_path.read_bytes() != HOOK.read_bytes():
            raise TransitionError("terminal observer source changed")
        catalog = self._api("GET", "/api/plugin?directory=" +
                            urllib.parse.quote(self.directory))["data"]
        if (len(catalog) != len(BUILTINS) + 1
                or {p["id"] for p in catalog} != BUILTINS | {PLUGIN_ID}
                or any(p["state"]["status"] != "active" for p in catalog)
                or any(p["source"]["type"] != "builtin" for p in catalog if p["id"] in BUILTINS)
                or not any(p["id"] == PLUGIN_ID and p["source"].get("type") == "local"
                    and Path(p["source"]["path"]).resolve() == self.host.plugin_path for p in catalog)):
            raise TransitionError("unknown plugin graph; receipt disabled")
        agent = self._api("GET", "/api/agent/build?directory=" +
                          urllib.parse.quote(self.directory))["data"]
        if (agent.get("id") != "build" or not agent.get("permissions")
                or agent["permissions"][-1] != {"action": "*", "resource": "*", "effect": "deny"}):
            raise TransitionError("bounded text profile requires native deny-all tool permissions")

    def _receipt_ready(self):
        # R3 completion still requires intact SSE. R4 receipt uses API/SQLite/hook.
        self.store._ready()
        self._graph()
        if (self.stopped or self._closed.is_set() or self.host.closed
                or self.host.adapter is not self or not self.owner_alive()
                or self.deadline is not None and time.monotonic() >= self.deadline):
            raise TransitionError("receipt owner/lifecycle/deadline invalid")

    def _invalidate(self, reason, *, stop=True):
        for candidate in (self.candidate, self.task_candidate):
            if candidate is not None:
                candidate["valid"] = False
                candidate["reason"] = reason
                candidate["release"].set()
        if stop and not self.stopped:
            self.stopped = True
            self.core.fail(reason)
            self._record("receipt_invalidated", reason=reason)

    def _stop(self, reason):
        with self.host.lock:
            self._invalidate(reason)
        raise TransitionError(reason)

    def close(self):
        with self.host.lock:
            self._invalidate("receipt attachment disposed", stop=False)
            super().close()

    def continue_task(self, text, *, ttl=30.0):
        """Claim before I/O; admit one actual input while the HTTP gate holds it."""
        with self.host.lock:
            if (not hasattr(self, "resume_qualification") or not self.resume_qualification["unresolved_work"]
                    or hasattr(self, "task_claim_snapshot") or text != self.resume_qualification["next_action"]
                    or ttl <= 0):
                raise TransitionError("one freshly reassessed unresolved action required")
            try:
                if (self._post_receipt() != self.resume_observation
                        or self.core.snapshot != self.resume_snapshot):
                    raise TransitionError("resume qualification changed before claim")
                permit = self.core.claim_continuation(expected_snapshot=self.resume_snapshot)
                self.task_claim_snapshot = self.core.snapshot
                self.task_text = text
                self.deadline = time.monotonic() + ttl
                self._record("continuation_claimed", permit=permit, snapshot=encode(self.task_claim_snapshot))
                admission = self._api("POST", "/api/session/" + self.core.snapshot.thread_id + "/prompt",
                                      {"text": text})["data"]
                if (admission.get("sessionID") != self.core.snapshot.thread_id
                        or admission.get("type") != "user" or not admission.get("id")
                        or admission["id"] in {m["id"] for m in self.resume_observation[1]["context"]}
                        or admission.get("payload", {}).get("text") != text):
                    raise TransitionError("continuation admission identity mismatch")
                self.task_input_id = admission["id"]
                self._record("continuation_input_admitted", admission=admission)
                return admission
            except Exception:
                self._invalidate("continuation send/admission uncertain; no retry")
                raise

    def _native_state(self):
        """Bracket an independent transcript/queue transaction with fresh API reads."""
        before = self.current_state()
        sid = self.core.snapshot.thread_id
        with closing(sqlite3.connect(self.db_path.as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("BEGIN")
            rows = db.execute("select id,type,seq,time_updated,data from session_message "
                "where session_id=? order by seq", (sid,)).fetchall()
            pending = db.execute("select id from session_pending where session_id=?", (sid,)).fetchall()
            inbox = db.execute("select id from session_inbox where session_id=?", (sid,)).fetchall()
        state = self.current_state()
        compact = [r for r in rows if r[0] == self.core.snapshot.binding.native_id]
        native = [dict(json.loads(r[4]), id=r[0], type=r[1]) for r in rows
                  if compact and r[2] >= compact[0][2]]
        if state != before or len(compact) != 1 or native != state["context"] or pending or inbox:
            raise TransitionError("native context/readback changed or pending work exists")
        self._no_tools(state)
        return state, rows

    def _post_receipt(self):
        """New API/SQLite/current reads after settlement; no cached gate proof."""
        self._receipt_ready()
        s, c = self.core.snapshot, self.candidate
        document = self.store.read_handoff(s.handoff.handoff_id)
        if (document != self.document or document.request != s.request
                or document.revisions != s.checkpoint.revisions or document.workspace != s.workspace
                or document.cwd != self.directory or s.handoff.continuation_turn_id
                or s.continuation_request_id is not None
                or not c or not c["valid"] or not c["authorized"] or not c["sealed"]):
            raise TransitionError("old handoff or replaced receipt attempt")
        current = self.observe_current()
        expected = CurrentContext(document.recovered.logical_task_id,
            s.revisions.intent_revision, s.revisions.execution_revision, s.workspace)
        state, rows = self._native_state()
        tail = state["context"][len(self.admitted_context):]
        if (current != expected or self.observe_current() != current
                or not self._settled(state) or state["active"]
                or state["context"][:len(self.admitted_context)] != self.admitted_context
                or len(tail) != 3 or tail[0].get("id") != self.native_id
                or tail[0].get("type") != "user" or tail[0].get("text") != self.payload
                or sha256(tail[0]["text"].encode()).hexdigest() != self.payload_hash
                or tail[1].get("type") != "assistant" or tail[1].get("finish") != "stop"
                or tail[2].get("type") != "idle" or tail[2].get("outcome") != "succeeded"
                or state["session"].get("model") != c["model"]):
            raise TransitionError("stale post-receipt task, context, queues or Session")
        self._no_tools(state)
        return current, state, rows

    def qualify_resume(self, *, reassess):
        """Reconcile fresh settled state before a separate task claim.

        The trusted bounded-task observer reads actual task state and returns the
        still-required next action, or None if complete. Historical text alone
        is insufficient. This assessment is not ResumeProof or task completion.
        """
        with self.host.lock:
            s = self.core.snapshot
            if (self.stopped or s.state != State.HANDOFF_RECEIVED or not s.receipt_evidence
                    or hasattr(self, "resume_qualification")):
                raise TransitionError("one received handoff required for resume qualification")
            try:
                current, state, rows = self._post_receipt()
                ref = self._record("post_receipt_observed", current=asdict(current),
                    state=state, sqlite_rows=rows, receipt_evidence=s.receipt_evidence,
                    host_local_attempt_id=self.candidate["id"])
                next_action = reassess(self.document, current, state)
                if (next_action is not None and (not isinstance(next_action, str) or not next_action
                        or not self.document.recovered.unresolved
                        or next_action != self.document.recovered.next_action_candidate)):
                    raise TransitionError("changed next action or unresolved work unknown")
                final = self._post_receipt()
                if final != (current, state, rows):
                    raise TransitionError("post-receipt state changed during reassessment")
                final_ref = self._record("post_receipt_final_observed", current=asdict(current),
                    state=final[1], sqlite_rows=final[2])
                self.core.reconcile_resume_context(intent_revision=current.intent_revision,
                    execution_revision=current.execution_revision, workspace=current.workspace)
                result = dict(fresh_state="PASS", current=asdict(current),
                    same_logical_task=True, unresolved_work=next_action is not None,
                    next_action=next_action, historical_next_action_reevaluated=True,
                    observation_ref=ref, final_observation_ref=final_ref,
                    continuation_authorized=False, resume_verified="NOT_REACHED",
                    stop_reason=None if next_action is not None else "no unresolved work")
                self._record("resume_qualified", **result)
                self.resume_qualification = result
                self.resume_observation = final
                self.resume_snapshot = self.core.snapshot
                return result
            except Exception:
                self._invalidate("post-receipt reconciliation failed; no continuation")
                raise

    def _task_fresh(self, *, context=None):
        self._receipt_ready()
        current = self.observe_current()
        state, rows = self._native_state()
        prefix = self.resume_observation[1]["context"]
        tail = state["context"][len(prefix):]
        if (current != self.resume_observation[0] or self.observe_current() != current
                or state["context"][:len(prefix)] != prefix or len(tail) not in (1, 2)
                or tail[0].get("type") != "user" or tail[0].get("text") != self.task_text
                or tail[0]["id"] in {m["id"] for m in prefix}
                or hasattr(self, "task_input_id") and tail[0]["id"] != self.task_input_id
                or len(tail) == 2 and (tail[1].get("type") != "assistant" or tail[1].get("content"))
                or state["inbox"] or set(state["active"]) != {self.core.snapshot.thread_id}
                or state["active"][self.core.snapshot.thread_id].get("type") != "running"
                or state["session"].get("model") != self.candidate["model"]
                or context is not None and state["context"] != context):
            raise TransitionError("task input, context or revision stale/foreign")
        return current, state, rows, tail[0]["id"]

    def _current_task_attempt(self, identity):
        self._receipt_ready()
        c, s = self.task_candidate, self.core.snapshot
        if (not c or not c["valid"] or c["id"] != identity or c["id"] == self.candidate["id"]
                or s.state != State.HANDOFF_RECEIVED or not hasattr(self, "task_claim_snapshot")
                or s.continuation_request_id != self.task_claim_snapshot.continuation_request_id):
            raise TransitionError("old/consumed task attempt")
        return c

    def authorize_continuation(self, identity):
        with self.host.lock:
            try:
                c = self._current_task_attempt(identity)
                if c["authorized"] or c["sealed"]:
                    raise TransitionError("duplicate task authorization")
                current, state, rows, native_id = self._task_fresh(context=c["context"])
                if native_id != c["native_id"] or native_id != self.task_input_id:
                    raise TransitionError("actual admission/readback identity mismatch")
                binding = ContinuationBinding(self.task_claim_snapshot.continuation_request_id,
                    self.core.snapshot.thread_id, native_id)
                self.receipt_policy.delivery = binding
                self.core.bind_continuation(binding, expected_snapshot=self.task_claim_snapshot)
                c["binding_snapshot"] = self.core.snapshot
                c["binding_ref"] = self._record("continuation_bound", binding=asdict(binding),
                    snapshot=encode(self.core.snapshot), state=state, sqlite_rows=rows)
                self._task_fresh(context=c["context"])
                if self.core.snapshot != c["binding_snapshot"]:
                    raise TransitionError("task binding changed before authorization")
                c["authorization_ref"] = self._record("task_attempt_authorized", host_local_attempt_id=identity,
                    native_id=native_id, binding_ref=c["binding_ref"], current=asdict(current))
                c["authorized"] = True
                c["release"].set()
                return True
            except Exception:
                self._invalidate("task authorization rejected; claim/binding retained")
                return False

    def complete_continuation(self):
        """Observe completion without claiming ResumeProof compatibility."""
        with self.host.lock:
            c = self.task_candidate
            if (not c or not c["sealed"] or hasattr(self, "task_completion")):
                raise TransitionError("one released continuation required")
            try:
                self._receipt_ready()
                self._api("POST", "/api/experimental/session/" + self.core.snapshot.thread_id + "/wait")
                observation = self._task_final()
                self.task_completion = self._record("continuation_completed", current=asdict(observation[0]),
                    state=observation[1], sqlite_rows=observation[2], native_id=self.task_input_id,
                    host_local_attempt_id=c["id"], resume_proof="BLOCKED_BY_EXISTING_CONTRACT")
                return observation[1]
            except Exception:
                self._invalidate("continuation completion uncertain; no retry")
                raise

    def _task_final(self):
        self._receipt_ready()
        current = self.observe_current()
        state, rows = self._native_state()
        prefix = self.resume_observation[1]["context"]
        tail = state["context"][len(prefix):]
        if (self.observe_current() != current or current.logical_task_id != self.document.recovered.logical_task_id
                or not self._settled(state) or state["active"] or state["inbox"]
                or state["session"].get("model") != self.candidate["model"]
                or state["context"][:len(prefix)] != prefix or len(tail) != 3
                or tail[0].get("id") != self.task_input_id or tail[0].get("type") != "user"
                or tail[0].get("text") != self.task_text or tail[1].get("type") != "assistant"
                or tail[1].get("finish") != "stop" or tail[2].get("type") != "idle"
                or self.core.snapshot.handoff.continuation_turn_id != self.task_input_id):
            raise TransitionError("final task context/identity/settlement mismatch")
        return current, state, rows

    def final_observation(self):
        with self.host.lock:
            if not hasattr(self, "task_completion") or hasattr(self, "task_final_observation"):
                raise TransitionError("one completed task required for final observation")
            try:
                before = self._task_final()
                after = self._task_final()
                if before != after:
                    raise TransitionError("final task observation changed")
                current, state, rows = after
                self.core.reconcile_resume_context(intent_revision=current.intent_revision,
                    execution_revision=current.execution_revision, workspace=current.workspace)
                self.task_final_observation = self._record("task_final_observed", current=asdict(current),
                    state=state, sqlite_rows=rows, snapshot=encode(self.core.snapshot),
                    resume_proof="BLOCKED_BY_EXISTING_CONTRACT", resume_verified="NOT_REACHED")
                return state
            except Exception:
                self._invalidate("final task observation uncertain; no retry")
                raise

    def offer_receipt(self, document):
        with self.host.lock:
            self._receipt_ready()
            s = self.core.snapshot
            if (s.state != State.ROLLOVER_OBSERVED or self.document is not None
                    or not isinstance(document, HandoffDocument) or document.request != s.request
                    or document.revisions != s.checkpoint.revisions
                    or document.workspace != s.workspace or document.cwd != self.directory
                    or document.recovered.archive_ids !=
                        self.store.checkpoint_archive_ids(s.checkpoint.checkpoint_id)):
                raise TransitionError("handoff differs from completed checkpoint/profile")
            try:
                self.store.commit_handoff(document)
                if self.store.read_handoff(document.handoff_id) != document:
                    raise TransitionError("durable handoff readback mismatch")
                self.document = document
                self.payload = document.render() + (
                    "\nReceipt inspection only. Reply RECEIPT_ONLY without tools. "
                    "Do not continue the task or repeat completed work.")
                self.payload_hash = sha256(self.payload.encode()).hexdigest()
                self.native_id = "msg_" + secrets.token_hex(13)
                self._record("handoff_delivery_requested", handoff_id=document.handoff_id,
                    native_id=self.native_id, payload_hash=self.payload_hash, permit=None)
                admission = self._api("POST", "/api/session/" + s.thread_id + "/prompt",
                    {"id": self.native_id, "text": self.payload, "resume": False})["data"]
                state = self.current_state()
                native = self._native("session_inbox")
                if (admission["sessionID"] != s.thread_id or admission["id"] != self.native_id
                        or admission["type"] != "user" or admission["payload"].get("text") != self.payload
                        or native != self.payload or sha256(native.encode()).hexdigest() != self.payload_hash
                        or state["inbox"] != [admission] or s.thread_id in state["active"]
                        or any(m["id"] == self.native_id for m in state["context"])):
                    raise TransitionError("non-waking admission identity/payload mismatch")
                self.admitted_context = state["context"]
                self.core.offer_handoff(None, recovered_context=self.payload,
                    handoff_id=document.handoff_id, expected_snapshot=s)
                self.injection = self._record("handoff_admitted_only", admission=admission,
                    payload_hash=self.payload_hash, independent_readback_hash=sha256(native.encode()).hexdigest(),
                    state=state, handoff=asdict(self.core.snapshot.handoff))
                return admission
            except Exception:
                self._invalidate("handoff delivery uncertain; no retry")
                raise

    def _native(self, table):
        column = "payload" if table == "session_inbox" else "data"
        with closing(sqlite3.connect(self.db_path.as_uri() + "?mode=ro", uri=True)) as db:
            rows = db.execute(f"select session_id, type, {column} from {table} where id=?",
                              (self.native_id,)).fetchall()
        if len(rows) != 1 or rows[0][:2] != (self.core.snapshot.thread_id, "user"):
            raise TransitionError("native delivery identity mismatch")
        return json.loads(rows[0][2]).get("text")

    def promote_receipt(self, *, ttl=30.0):
        with self.host.lock:
            self._receipt_ready()
            if self.core.snapshot.state != State.HANDOFF_OFFERED or self.promoted or ttl <= 0:
                raise TransitionError("one offered handoff promotion required")
            self.promoted = True
            self.deadline = time.monotonic() + ttl
            try:
                admitted = self._api("POST", "/api/session/" + self.core.snapshot.thread_id + "/prompt",
                    {"id": self.native_id, "text": self.payload})["data"]
                if (admitted["sessionID"] != self.core.snapshot.thread_id
                        or admitted["id"] != self.native_id or admitted["payload"].get("text") != self.payload):
                    raise TransitionError("native promotion identity/payload mismatch")
            except Exception:
                self._invalidate("native promotion uncertain; no retry")
                raise

    def _fresh(self, *, context=None):
        self._receipt_ready()
        s = self.core.snapshot
        current = self.observe_current()  # Execute a new trusted read; never accept a cached proof.
        expected = CurrentContext(self.document.recovered.logical_task_id,
            s.revisions.intent_revision, s.revisions.execution_revision, s.workspace)
        if current != expected or s.handoff.handoff_id != self.document.handoff_id:
            raise TransitionError("stale workspace/task/handoff observation")
        native = self._native("session_message")
        state = self.current_state()  # Fetch AFTER the independent SQLite read.
        messages = [m for m in state["context"] if m["id"] == self.native_id]
        if (len(messages) != 1 or messages[0]["type"] != "user"
                or messages[0].get("text") != self.payload or native != self.payload
                or sha256(native.encode()).hexdigest() != self.payload_hash
                or state["inbox"] or set(state["active"]) != {s.thread_id}
                or state["active"][s.thread_id].get("type") != "running"
                or state["context"][:len(self.admitted_context)] != self.admitted_context
                or any(m["type"] == "user" and m["id"] != self.native_id
                       for m in state["context"][len(self.admitted_context):])
                or any(m.get("content") for m in state["context"][len(self.admitted_context):]
                       if m["type"] == "assistant")
                or context is not None and state["context"] != context):
            raise TransitionError("native input/current context changed")
        self._no_tools(state)
        return current, state

    def _current_attempt(self, identity):
        self._receipt_ready()
        c = self.candidate
        if (not c or not c["valid"] or c["id"] != identity
                or self.core.snapshot.state != State.HANDOFF_OFFERED):
            raise TransitionError("old/consumed receipt attempt")
        return c

    def authorize_receipt(self, identity):
        with self.host.lock:
            try:
                c = self._current_attempt(identity)
                if c["authorized"]:
                    raise TransitionError("duplicate authorization")
                current, state = self._fresh(context=c["context"])
                self._current_attempt(identity)
                c["fresh"] = asdict(current)
                c["authorized"] = True
                c["authorization_ref"] = self._record("receipt_attempt_authorized",
                    host_local_attempt_id=identity, fresh_observation=c["fresh"], state=state)
                c["release"].set()
                return True
            except Exception:
                self._invalidate("receipt authorization rejected")
                return False

    def abort_receipt(self, reason="owner interrupt"):
        with self.host.lock:
            self._invalidate(reason)
        # Invalidation precedes native cancellation: old JS Promises can finish late.
        self._api("POST", "/api/session/" + self.core.snapshot.thread_id + "/interrupt")

    def _hook(self, path, data):
        with self.host.lock:
            try:
                self._receipt_ready()
                if path in ("/retry", "/invalidate"):
                    self._invalidate("native retry/provider failure" if path == "/retry"
                                     else "terminal body changed")
                    return {"action": "deny"}
                if path == "/seal":
                    if self.task_candidate is not None and data["id"] == self.task_candidate["id"]:
                        c = self._current_task_attempt(data["id"])
                        if (not c["authorized"] or c["sealed"]
                                or data["body_sha256"] != c["body_sha256"]
                                or self.core.snapshot != c["binding_snapshot"]):
                            raise TransitionError("task terminal body/binding mismatch")
                        current, state, rows, native_id = self._task_fresh(context=c["context"])
                        if native_id != self.core.snapshot.handoff.continuation_turn_id:
                            raise TransitionError("task identity changed after binding")
                        c["seal_ref"] = self._record("task_terminal_sealed", host_local_attempt_id=c["id"],
                            native_id=native_id, terminal_body_hash=c["body_sha256"],
                            binding_ref=c["binding_ref"], authorization_ref=c["authorization_ref"],
                            current=asdict(current), state=state, sqlite_rows=rows)
                        c["sealed"] = True
                        return {"id": c["id"], "action": "allow"}
                    c = self._current_attempt(data["id"])
                    if (not c["authorized"] or c["sealed"]
                            or data["body_sha256"] != c["body_sha256"]):
                        raise TransitionError("terminal body/authorization mismatch")
                    current, state = self._fresh(context=c["context"])
                    self._current_attempt(data["id"])
                    c["sealed"] = True
                    ref = self._record("terminal_request_receipt",
                        handoff_id=self.document.handoff_id, native_id=self.native_id,
                        payload_hash=self.payload_hash, host_local_attempt_id=c["id"],
                        terminal_body_hash=c["body_sha256"], request_kind=c["kind"], model=c["model"],
                        fresh_observation_revision=asdict(current), authorization_result="one-shot allowed",
                        authority="pre-send exact provider request incorporation", state=state,
                        authorization_ref=c["authorization_ref"])
                    if not self.core.receive_handoff(self.core.snapshot.handoff,
                            injection_evidence=c["observation_ref"], receipt_evidence=ref):
                        raise TransitionError("duplicate receipt")
                    self._record("handoff_received", receipt_evidence=ref)
                    return {"id": c["id"], "action": "allow"}
                if path != "/observe":
                    raise TransitionError("unknown receipt callback")
                epoch, counter = data["id"].rsplit(":", 1)
                if epoch != self.host.epoch or int(counter) != self.host.counter + 1:
                    raise TransitionError("stale/foreign hook invocation")
                self.host.counter = int(counter)
                if (data["sessionID"] != self.core.snapshot.thread_id or data["agent"] != "build"
                        or data["model"] != self.current_state()["session"]["model"]
                        or data["method"] != "POST" or data["url"] != self.provider_request_url):
                    raise TransitionError("foreign provider request scope")
                raw = base64.b64decode(data["body_base64"], validate=True)
                if sha256(raw).hexdigest() != data["body_sha256"]:
                    raise TransitionError("terminal observer body hash mismatch")
                body = json.loads(raw)
                if body.get("tools"):
                    raise TransitionError("tool definitions forbidden in bounded text profile")
                if self.document is None:
                    # Initial bounded work and native compact; never a receipt.
                    if data["kind"] not in ("primary", "compaction"):
                        raise TransitionError("auxiliary request outside profile")
                    return {"id": data["id"], "action": "allow", "gated": False}
                if hasattr(self, "task_claim_snapshot"):
                    if (self.task_candidate is not None or data["kind"] != "primary"
                            or self.core.snapshot != self.task_claim_snapshot
                            or body.get("model") != data["model"]["id"]
                            or sum(m.get("role") == "user" and m.get("content") == self.task_text
                                   for m in body.get("messages", [])) != 1
                            or [m for m in body.get("messages", []) if m.get("role") == "user"][-1]
                                   .get("content") != self.task_text):
                        raise TransitionError("task request replaced/retried/foreign")
                    current, state, rows, native_id = self._task_fresh()
                    ref = self._record("task_terminal_observed", host_local_attempt_id=data["id"],
                        native_id=native_id, terminal_body_hash=data["body_sha256"],
                        state=state, sqlite_rows=rows, current=asdict(current))
                    c = dict(id=data["id"], purpose="task", native_id=native_id,
                        body_sha256=data["body_sha256"], context=state["context"], observation_ref=ref,
                        valid=True, authorized=False, sealed=False, release=threading.Event())
                    self.task_candidate = c
                    self.task_observed.set()
                else:
                    c = self._observe_receipt(data, body)
            except Exception as exc:
                reason = str(exc) if isinstance(exc, TransitionError) else type(exc).__name__
                self._invalidate("receipt/task callback rejected: " + reason)
                return {"id": data.get("id"), "action": "deny"}
        c["release"].wait(max(0, self.deadline - time.monotonic()))
        with self.host.lock:
            try:
                if c.get("purpose") == "task":
                    self._current_task_attempt(c["id"])
                else:
                    self._current_attempt(c["id"])
                if not c["authorized"]:
                    raise TransitionError("attempt deadline expired")
                return {"id": c["id"], "action": "allow", "gated": True}
            except Exception:
                self._invalidate("attempt invalidated/expired")
                return {"id": c["id"], "action": "deny"}

    def _observe_receipt(self, data, body):
        # Called only under the owner lock after common scope/body/safety checks.
        if (not self.promoted or self.candidate is not None
                or self.core.snapshot.state != State.HANDOFF_OFFERED or data["kind"] != "primary"):
            raise TransitionError("attempt replaced/retried/consumed")
        if (body.get("model") != data["model"]["id"]
                or sum(m.get("role") == "user" and m.get("content") == self.payload
                       for m in body.get("messages", [])) != 1):
            raise TransitionError("exact handoff absent from actual provider body")
        current, state = self._fresh()
        ref = self._record("terminal_request_observed", host_local_attempt_id=data["id"],
            native_id=self.native_id, payload_hash=self.payload_hash,
            terminal_body_hash=data["body_sha256"], request_kind=data["kind"], model=data["model"],
            fresh_observation_revision=asdict(current), state=state)
        c = dict(id=data["id"], kind=data["kind"], model=data["model"],
            body_sha256=data["body_sha256"], context=state["context"], observation_ref=ref,
            valid=True, authorized=False, sealed=False, release=threading.Event())
        self.candidate = c
        self.observed.set()
        return c
