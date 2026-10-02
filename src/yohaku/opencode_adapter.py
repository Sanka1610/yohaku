"""Server/API adapter for one foreground task and one native compaction.

The owner serializes all methods; the SSE worker only queues observations.
The host guarantees an exclusive fresh session, disabled automatic compaction,
no additional compaction plugins, DCP or subagents, and supplies trusted task /
workspace boundary verification. No runtime-wide freeze or receipt is implied.
"""

from contextlib import closing
from dataclasses import asdict
import json
from pathlib import Path
import queue
import sqlite3
import threading
import time
import urllib.request

from .controller import Controller, TransitionError
from .model import State
from .opencode import (OPENCODE_VERSION, OpenCodeCompactBinding,
                       OpenCodeNativeCompletion, OpenCodeNativeCompletionPolicy)
from .persistence import _mkdir


class OpenCodeAdapter:
    def __init__(self, store, *, server_url, session_id, db_path,
                 exclusive_fresh_session, headers=None, timeout=120.0):
        if (exclusive_fresh_session is not True or store.thread_id != session_id
                or store.latest is not None or tuple(store.checkpoints.iterdir())
                or tuple(store.journal.iterdir()) or timeout <= 0):
            raise TransitionError("OpenCode needs a fresh, exclusive session and store")
        self.store, self.server_url = store, server_url.rstrip("/")
        self.db_path = Path(db_path).resolve()
        self.headers, self.timeout = dict(headers or {}), timeout
        self.core = self._controller(session_id)
        self.records = store.path / "opencode-evidence"
        _mkdir(self.records)
        self.record_seq = 0
        self.stopped = False
        self.dispatched = False
        self.started = self.ended = None
        self.before_ids = ()
        self._events = queue.Queue()
        self._connected = threading.Event()
        self._lost = threading.Event()
        self._closed = threading.Event()
        self._stream = None
        info = self._api("GET", "/api/info")
        if info.get("version") != OPENCODE_VERSION:
            raise TransitionError("OpenCode server must be 2.0.21")
        state = self.current_state()
        if state["context"] or state["inbox"] or session_id in state["active"]:
            raise TransitionError("OpenCode native session is not fresh and inactive")
        self.directory = state["session"]["location"]["directory"]
        self._record("attached", info=info, state=state)
        self._reader = threading.Thread(target=self._read_events, daemon=True)
        self._reader.start()
        if not self._connected.wait(min(timeout, 10)) or self._lost.is_set():
            self.close()
            raise TransitionError("OpenCode SSE subscription unavailable")

    def _controller(self, session_id):
        return Controller(session_id, completion_policy=OpenCodeNativeCompletionPolicy())

    def _api(self, method, path, body=None):
        request = urllib.request.Request(self.server_url + path, method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={**self.headers, "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            raw = response.read()
        return json.loads(raw) if raw else None

    def _record(self, kind, **data):
        self.record_seq += 1
        path = self.records / f"{self.record_seq:06d}.json"
        try:
            self.store._write(path, dict(kind=kind, session_id=self.core.snapshot.thread_id,
                                         observed=time.time(), **data))
        except Exception:
            self.stopped = True
            if self.core.snapshot.state != State.RESUME_VERIFIED:
                self.core.fail("OpenCode evidence write uncertain")
            raise
        return str(path)

    def _ready(self):
        self.store._ready()
        if self.stopped or self._closed.is_set():
            raise TransitionError("OpenCode attachment stopped")
        if self._lost.is_set():
            self._stop("OpenCode SSE observation lost")

    def _stop(self, reason):
        self.stopped = True
        if self.core.snapshot.state in (State.ROLLOVER_REQUESTED, State.AMBIGUOUS):
            self.core.completion_unknown(reason)
        else:
            self.core.fail(reason)
        raise TransitionError(reason)

    def _read_events(self):
        try:
            request = urllib.request.Request(self.server_url + "/api/event", headers=self.headers)
            with urllib.request.urlopen(request, timeout=self.timeout) as stream:
                self._stream = stream
                parts = []
                for raw in stream:
                    if self._closed.is_set():
                        return
                    line = raw.decode().rstrip("\r\n")
                    if line.startswith("data:"):
                        parts.append(line[5:].lstrip(" "))
                    elif not line and parts:
                        event = json.loads("\n".join(parts))
                        parts = []
                        self._events.put(event)
                        if event.get("type") == "server.connected":
                            self._connected.set()
            if not self._closed.is_set():
                self._lost.set()
        except Exception:
            if not self._closed.is_set():
                self._lost.set()

    def close(self):
        self._closed.set()
        # The daemon reader exits on EOF/socket timeout. Do not block the owner
        # on HTTPResponse.close while its read holds the buffered-reader lock.

    def current_state(self):
        sid = self.core.snapshot.thread_id
        state = {name: self._api("GET", "/api/session/" + sid + suffix)["data"]
                 for name, suffix in (("session", ""), ("inbox", "/inbox"),
                                      ("context", "/context"))}
        state["active"] = self._api("GET", "/api/session/active")["data"]
        if (state["session"]["id"] != sid or (hasattr(self, "directory")
                and state["session"]["location"]["directory"] != self.directory)):
            self._stop("OpenCode session identity/location changed")
        return state

    def _settled(self, state):
        return (self.core.snapshot.thread_id not in state["active"] and not state["inbox"]
                and state["session"].get("outcome") == "succeeded"
                and bool(state["context"]) and state["context"][-1].get("type") == "idle"
                and state["context"][-1].get("outcome") == "succeeded")

    def _no_tools(self, state):
        # Only the explicitly bounded text task is covered by this attachment.
        if any(part.get("type") == "tool" for message in state["context"]
               for part in message.get("content", [])):
            self._stop("tool work is outside the OpenCode foreground text profile")

    def work(self, text):
        self._ready()
        self.core.require_work()
        if getattr(self, "work_id", None):
            raise TransitionError("only one foreground task is covered")
        self.work_id = "dispatching"
        try:
            self._record("work_requested", text=text)
            admission = self._api("POST", "/api/session/" + self.core.snapshot.thread_id + "/prompt",
                                  {"text": text})["data"]
            self.work_id = admission["id"]
            state = self._wait_settled()
            self._no_tools(state)
            if not any(m["id"] == self.work_id and m["type"] == "user" for m in state["context"]):
                self._stop("foreground prompt absent from current context")
            self._record("work_settled", admission=admission, state=state)
            return state
        except Exception:
            if not self.stopped:
                self._stop("OpenCode foreground work uncertain")
            raise

    def _wait_settled(self):
        self._api("POST", "/api/experimental/session/" + self.core.snapshot.thread_id + "/wait")
        self._ready()
        state = self.current_state()
        if not self._settled(state):
            self._stop("OpenCode foreground settlement incomplete")
        return state

    def checkpoint(self, *, boundary_id, verification, observe_workspace):
        self._ready()
        if not getattr(self, "work_id", None):
            raise TransitionError("bounded work must precede checkpoint")
        state = self.current_state()
        if not self._settled(state):
            self._stop("OpenCode work remains at boundary")
        self._no_tools(state)
        workspace = observe_workspace()
        self.core.propose_boundary(boundary_id)
        self.core.arm_barrier()
        self.core.begin_quiescence_check()
        self.core.observe_quiescence(relevant_work_remaining=False)
        self.core.capture_workspace(workspace)
        self.core.verify_boundary(verification)
        cp = self.store.commit_checkpoint(self.core.prepare_checkpoint())
        self.core.checkpoint_committed(cp.checkpoint_id, commit_evidence=cp.commit_evidence)
        self.store.append(self.core.snapshot, {}, "opencode_checkpoint")
        self._record("verified_boundary", state=state, checkpoint_id=cp.checkpoint_id)
        return cp

    def compact(self, *, observe_workspace, now=time.monotonic, ttl=30.0):
        self._ready()
        if self.dispatched:
            raise TransitionError("OpenCode compact already dispatched")
        lease = self.core.authorize_rollover(now=now(), ttl=ttl)
        state = self.current_state()
        if not self._settled(state):
            self._stop("OpenCode work changed before dispatch")
        self._drain_events()
        workspace = observe_workspace()
        self._ready()
        s = self.core.snapshot
        request = self.core.request_rollover(lease, now=now(),
            intent_revision=s.revisions.intent_revision, execution_revision=s.revisions.execution_revision,
            workspace=workspace)
        self.dispatched = True
        self.before_ids = tuple(m["id"] for m in state["context"])
        try:
            self.store.append(self.core.snapshot, {}, "opencode_compact_requested")
            self._record("compact_requested", request=asdict(request), before=state)
            admission = self._api("POST", "/api/session/" + request.thread_id + "/compact", {})["data"]
            if admission["sessionID"] != request.thread_id or admission["type"] != "compaction":
                self._stop("OpenCode admission mismatch")
            binding = OpenCodeCompactBinding(request, request.thread_id, self.server_url,
                                             self.directory, admission["id"])
            self._record("compact_admitted", admission=admission, binding=asdict(binding))
            self.core.accept_request(request)
            self.core.bind_completion(binding)
            # Request success has made no completion claim. The SSE worker may
            # already have queued started/ended while HTTP returned admission.
            state = self._wait_settled()
            deadline = time.monotonic() + self.timeout
            while self.ended is None:
                self._drain_events()
                if time.monotonic() >= deadline:
                    self._stop("OpenCode native lifecycle incomplete")
                if self.ended is None:
                    time.sleep(0.02)
            return self._complete()
        except Exception:
            if not self.stopped:
                self._stop("OpenCode compact/readback uncertain; no retry")
            raise

    def _drain_events(self):
        self._ready()
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            if (event.get("data", {}).get("sessionID") != self.core.snapshot.thread_id
                    or not event.get("type", "").startswith("session.compaction.")):
                continue
            if event["type"] == "session.compaction.delta":
                continue
            self._record("native_lifecycle", event=event)
            binding = self.core.snapshot.binding
            if binding is None:
                self._stop("unexpected native compaction before admission")
            if event["type"] == "session.compaction.started":
                if (event.get("data", {}).get("inputID") != binding.native_id
                        or (self.started is not None and self.started != event)):
                    self._stop("conflicting OpenCode native start")
                self.started = event
            elif event["type"] == "session.compaction.ended":
                if self.started is None or (self.ended is not None and self.ended != event):
                    self._stop("OpenCode ended without a unique matching start")
                self.ended = event
            elif event["type"] == "session.compaction.failed":
                self._stop("OpenCode native compaction failed")
        self._ready()

    def _complete(self):
        self._ready()
        binding = self.core.snapshot.binding
        with closing(sqlite3.connect(self.db_path.as_uri() + "?mode=ro", uri=True)) as db:
            row = db.execute("select type, seq, time_updated, data from session_message "
                             "where session_id=? and id=?",
                             (binding.session_id, binding.native_id)).fetchone()
        if row is None:
            self._stop("OpenCode independent SQLite readback absent")
        sqlite_message = dict(json.loads(row[3]), id=binding.native_id, type=row[0])
        # Fetch again AFTER native completion and the independent DB connection.
        state = self.current_state()
        self._drain_events()
        messages = [m for m in state["context"] if m["id"] == binding.native_id]
        if len(messages) != 1:
            self._stop("OpenCode fresh context lacks admitted compaction")
        fields = dict(started=self.started, ended=self.ended, context_message=messages[0],
            sqlite_message=sqlite_message, sqlite_seq=row[1], sqlite_updated=row[2],
            before_ids=self.before_ids, current_ids=tuple(m["id"] for m in state["context"]),
            session_after=state["session"]["id"], settled=self._settled(state),
            observation_intact=not self._lost.is_set())
        ref = self._record("completion_readback", state=state, **fields)
        proof = OpenCodeNativeCompletion(binding, ref, **fields)
        self._ready()
        if not self.core.observe_completion(proof):
            self._stop("OpenCode completion proof rejected")
        self._record("rollover_observed", proof=asdict(proof))
        return proof

    def continue_task(self, text):
        self._ready()
        permit = self.core.claim_continuation()
        try:
            self._record("continuation_requested", permit=permit, text=text)
            admission = self._api("POST", "/api/session/" + self.core.snapshot.thread_id + "/prompt",
                                  {"text": text})["data"]
            state = self._wait_settled()
            self._drain_events()
            self._no_tools(state)
            ids = [m["id"] for m in state["context"]]
            if admission["id"] in self.before_ids or admission["id"] not in ids:
                self._stop("OpenCode continuation input identity mismatch")
            self._record("continuation_settled", admission=admission, state=state,
                         receipt="UNSUPPORTED", resume_verified="NOT_ASSESSED")
            return state
        except Exception:
            if not self.stopped:
                self._stop("OpenCode continuation uncertain; no retry")
            raise
