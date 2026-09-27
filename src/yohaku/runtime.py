"""Serialized Codex App Server event loop and synchronous local Hook bridge."""

import json
from pathlib import Path
import queue
import socket
import tempfile
import threading
import time

from .controller import TransitionError
from .model import State


class HookBridge:
    """Private per-process socket. The background thread never mutates Core/store."""

    def __init__(self, *, timeout=5.0):
        self.timeout = timeout
        self.pending = queue.Queue()
        self._directory = tempfile.TemporaryDirectory(prefix="yohaku-hook-")
        self.path = str(Path(self._directory.name) / "owner.sock")
        self._socket = socket.socket(socket.AF_UNIX)
        self._socket.bind(self.path)
        self._socket.listen(4)
        self._socket.settimeout(0.1)
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        while not self._closed.is_set():
            try:
                connection, _ = self._socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with connection:
                connection.settimeout(self.timeout)
                try:
                    with connection.makefile("rb") as stream:
                        line = stream.readline(65537)
                        if len(line) > 65536 or not line.endswith(b"\n"):
                            continue
                        payload = json.loads(line)
                        if not isinstance(payload, dict):
                            continue
                        response, ready = {}, threading.Event()
                        deadline = time.monotonic() + self.timeout
                        self.pending.put((payload, response, ready, deadline))
                        if ready.wait(self.timeout):
                            connection.sendall(json.dumps(response).encode() + b"\n")
                except (OSError, ValueError):
                    pass  # No raw Hook input or exception text is logged.

    def poll(self, recovery):
        try:
            payload, response, ready, deadline = self.pending.get_nowait()
        except queue.Empty:
            return False
        if time.monotonic() < deadline:
            try:
                response.update(recovery.deliver(payload))
            except TransitionError:
                pass  # Runtime may fail open; no receipt/verification is inferred.
        elif hasattr(recovery, "hook_expired"):
            recovery.hook_expired(payload)
        ready.set()
        return True

    def close(self):
        self._closed.set()
        self._socket.close()
        # Wake a pending request so shutdown does not wait for a Hook timeout.
        while True:
            try:
                _, _, ready, _ = self.pending.get_nowait()
                ready.set()
            except queue.Empty:
                break
        self._thread.join(timeout=1)
        self._directory.cleanup()


class RuntimeHost:
    """Pump one initialized, exclusively owned JSONL connection on its owner thread.

    Process launch/auth/trust remain explicit host concerns. Read timeout is
    serviced independently of App Server output, including while a Hook waits.
    A restarted host cannot guess missing turn bindings from a new stream.
    """

    def __init__(self, companion, stream=None, *, bridge=None, on_unhandled=None,
                 work_cwd=None, archive=None):
        self.companion = companion
        self.bridge = bridge
        self.on_unhandled = on_unhandled
        if archive is not None and archive.owner is not companion:
            raise ValueError("archive adapter must share the Runtime owner")
        self.archive = archive
        self.native = None
        from .work import WorkPlane
        self.work = WorkPlane(companion, cwd=work_cwd) if work_cwd is not None else None
        self.messages = queue.Queue()
        self.request = companion.snapshot.request
        self.deadline = None
        self._reader = None
        if stream is not None:
            self._reader = threading.Thread(target=self._read, args=(stream,), daemon=True)
            self._reader.start()

    def _read(self, stream):
        try:
            for line in stream:
                self.messages.put(json.loads(line))
        except (OSError, ValueError):
            pass
        finally:
            self.messages.put(None)

    def request_compact(self, lease, observe, **kwargs):
        if self.work:
            self.work.require_quiescent()
        request = self.companion.request_compact(lease, observe, **kwargs)
        self.request = request
        return request

    def enable_native_recovery(self, **kwargs):
        from .native import NativeCompact
        if self.native is not None:
            raise TransitionError("native observer already attached")
        self.native = NativeCompact(self, **kwargs)
        return self.native

    def continue_task(self, recovered, *, cwd, observe, timeout=60.0, max_attempts=2):
        import math
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("positive continuation timeout required")
        ident = self.companion.recovery.start(recovered, cwd=cwd, observe=observe,
                                               max_attempts=max_attempts)
        self.deadline = time.monotonic() + timeout
        return ident

    def receive(self, message):
        if message is None:
            if self.native:
                self.native.receive(None)
            if self.archive:
                self.archive.receive(None)
            if self.work:
                self.work.receive(None)
            if self.companion.snapshot.state not in (State.WORKING, State.RESUME_VERIFIED):
                self.companion.step("fail", "runtime connection closed")
            return
        if not isinstance(message, dict):
            raise TransitionError("invalid Runtime envelope")
        if self.native:
            self.native.receive(message)
            if self.native.stopped:
                if self.work:
                    self.work.receive(message)
                return  # Never attribute an external compact to a pending manual request.
        if self.archive and self.archive.receive(message):
            return
        if self.work:
            self.work.receive(message)
        handled = self.companion.recovery.receive(message)
        if not handled:
            handled = self.companion.receive(message, request=self.request)
        if not handled and self.on_unhandled is not None:
            self.on_unhandled(message)

    def deliver(self, payload):
        if self.native:
            output = self.native.deliver(payload)
            if output is not None:
                return output
            if (self.native.stopped and payload.get("hook_event_name") == "SessionStart"
                    and payload.get("source") == "compact"):
                return {"continue": False}
        if self.work and payload.get("hook_event_name") in ("PreToolUse", "PostToolUse"):
            return self.work.deliver(payload)
        return self.companion.recovery.deliver(payload)

    def hook_expired(self, payload):
        if (self.native and payload.get("hook_event_name") == "PreCompact"
                and payload.get("session_id") == self.companion.snapshot.thread_id):
            self.native.stop()
        if (self.work and payload.get("hook_event_name") in ("PreToolUse", "PostToolUse")
                and payload.get("session_id") == self.companion.snapshot.thread_id):
            self.work.observation_lost()

    def poll(self, timeout=0.05):
        try:
            self.receive(self.messages.get(timeout=timeout))
        except queue.Empty:
            pass
        # Drain already queued Runtime ordering before servicing a Hook payload.
        for _ in range(256):
            try:
                self.receive(self.messages.get_nowait())
            except queue.Empty:
                break
        if self.bridge:
            self.bridge.poll(self)
        self.companion.poll_timeout()
        if self.native:
            self.native.poll()
        recovery = self.companion.recovery
        if self.deadline is not None and time.monotonic() >= self.deadline:
            self.deadline = None
            if recovery.cursor and not recovery.cursor.terminal:
                recovery.stop("continuation receipt/completion timeout")
