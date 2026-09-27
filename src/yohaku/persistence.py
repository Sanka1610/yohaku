"""POSIX durable checkpoint files and a small immutable-record journal."""

import hashlib
import json
import os
import re
import tempfile
from dataclasses import replace
from pathlib import Path

from .codec import decode, encode
from .model import Checkpoint, Snapshot


class PersistenceError(RuntimeError):
    pass


def resolve_yohaku_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    codex_home = Path(configured).expanduser() if configured else Path.home() / ".codex"
    if not codex_home.is_absolute():
        raise PersistenceError("CODEX_HOME must be absolute; cwd-relative storage is rejected")
    return codex_home.resolve() / "yohaku"


def _component(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,159}", value):
        raise PersistenceError("invalid storage identifier")
    return value


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _mkdir(path):
    if path.is_symlink():
        raise PersistenceError("symlink storage directory rejected")
    if path.exists():
        if not path.is_dir():
            raise PersistenceError("storage directory expected")
        return
    _mkdir(path.parent)
    path.mkdir(mode=0o700)
    _sync_directory(path.parent)


def _atomic_write(path, payload):
    """Only the final name is eligible for recovery; .tmp files are ignored."""
    if path.exists() or path.is_symlink():
        raise PersistenceError("immutable record already exists")
    fd, temporary = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _envelope(payload):
    return {"schema": 1, "sha256": hashlib.sha256(_json(payload)).hexdigest(), "payload": payload}


def _read(path):
    if path.is_symlink():
        raise PersistenceError("symlink record rejected")
    try:
        record = json.loads(path.read_bytes())
        if (set(record) != {"schema", "sha256", "payload"} or record["schema"] != 1
                or _envelope(record["payload"]) != record):
            raise ValueError("integrity or schema mismatch")
        return record
    except (OSError, TypeError, ValueError) as exc:
        raise PersistenceError("unreadable or corrupt durable record") from exc


class SessionStore:
    """One locally locked session. Existing sessions must be opened for recovery.

    Any write uncertainty poisons the open handle; close/reopen and reconcile.
    The local lock does not establish exclusive runtime ownership.
    """

    def __init__(self, thread_id: str, *, create=False):
        if os.name != "posix":
            raise PersistenceError("durable persistence currently requires POSIX")
        import fcntl

        self.thread_id = _component(thread_id)
        self.path = resolve_yohaku_home() / "sessions" / self.thread_id
        self._lock = None
        self._poisoned = False
        self._sequence = 0
        self._previous = None
        self.latest = None
        self.recovery = None
        if create:
            _mkdir(self.path.parent)
            self.path.mkdir(mode=0o700)  # deliberately exclusive, even after an interrupted create
            _sync_directory(self.path.parent)
        elif not self.path.is_dir() or self.path.is_symlink():
            raise PersistenceError("session missing; cannot silently start fresh")
        try:
            self._lock = os.open(self.path / "writer.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.checkpoints = self.path / "checkpoints"
            self.journal = self.path / "journal"
            if create:
                _mkdir(self.checkpoints)
                _mkdir(self.journal)
            else:
                if any(p.is_symlink() or not p.is_dir() for p in (self.checkpoints, self.journal)):
                    raise PersistenceError("incomplete session layout")
                self._load()
        except Exception:
            self.close()
            raise

    def close(self):
        if self._lock is not None:
            os.close(self._lock)
            self._lock = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _ready(self):
        if self._lock is None or self._poisoned:
            raise PersistenceError("store closed or write outcome uncertain; recover before continuing")

    def _write(self, path, payload):
        self._ready()
        try:
            _atomic_write(path, _json(_envelope(payload)))
        except Exception as exc:
            self._poisoned = True
            raise PersistenceError("durable write failed; no further dispatch allowed") from exc

    def commit_checkpoint(self, checkpoint: Checkpoint) -> Checkpoint:
        self._ready()
        checkpoint_id = _component(checkpoint.checkpoint_id)
        committed = replace(checkpoint, commit_evidence=f"checkpoint:{checkpoint_id}")
        path = self.checkpoints / f"{checkpoint_id}.json"
        if path.exists():
            if self.read_checkpoint(checkpoint_id) != committed:
                raise PersistenceError("checkpoint ID content conflict")
            _sync_directory(self.checkpoints)
        else:
            self._write(path, {"thread_id": self.thread_id, "checkpoint": encode(committed)})
        return committed

    def read_checkpoint(self, checkpoint_id):
        payload = _read(self.checkpoints / f"{_component(checkpoint_id)}.json")["payload"]
        try:
            if set(payload) != {"thread_id", "checkpoint"} or payload["thread_id"] != self.thread_id:
                raise ValueError("wrong checkpoint owner")
            checkpoint = decode(Checkpoint, payload["checkpoint"])
            if (checkpoint.checkpoint_id != checkpoint_id
                    or checkpoint.commit_evidence != f"checkpoint:{checkpoint_id}"):
                raise ValueError("checkpoint identity mismatch")
            return checkpoint
        except (TypeError, ValueError) as exc:
            raise PersistenceError("invalid checkpoint") from exc

    def recovery_candidates(self):
        return tuple(self.read_checkpoint(p.stem) for p in sorted(self.checkpoints.glob("*.json")))

    def commit_handoff(self, document):
        self._ready()
        from .recovery import HandoffDocument
        if not isinstance(document, HandoffDocument) or document.request.thread_id != self.thread_id:
            raise PersistenceError("wrong handoff owner")
        directory = self.path / "handoffs"
        _mkdir(directory)
        path = directory / f"{_component(document.handoff_id)}.json"
        if path.exists():
            if self.read_handoff(document.handoff_id) != document:
                raise PersistenceError("handoff ID conflict")
            _sync_directory(directory)
        else:
            self._write(path, encode(document))

    def read_handoff(self, handoff_id):
        from .recovery import HandoffDocument
        try:
            document = decode(HandoffDocument, _read(
                self.path / "handoffs" / f"{_component(handoff_id)}.json")["payload"])
            if document.handoff_id != handoff_id or document.request.thread_id != self.thread_id:
                raise ValueError("handoff identity mismatch")
            return document
        except (TypeError, ValueError) as exc:
            raise PersistenceError("invalid handoff") from exc

    def append(self, snapshot: Snapshot, cursor: dict, event: str, *, recovery=None):
        self._ready()
        if snapshot.thread_id != self.thread_id:
            raise PersistenceError("wrong session")
        if snapshot.handoff and snapshot.handoff.recovered_context != f"handoff:{snapshot.handoff.handoff_id}":
            raise PersistenceError("journal handoff must reference a separate durable document")
        _component(event)
        # Deadlines and active authority are intentionally absent from disk.
        saved = replace(snapshot, lease=None, reason=None,
                        revoked_lease_id=snapshot.lease.lease_id if snapshot.lease else snapshot.revoked_lease_id)
        payload = {"sequence": self._sequence + 1, "previous": self._previous,
                   "event": event, "snapshot": encode(saved), "cursor": cursor}
        if recovery is not None:
            payload["recovery"] = encode(recovery)
        self._write(self.journal / f"{self._sequence + 1:012d}.json", payload)
        self._sequence += 1
        self._previous = _envelope(payload)["sha256"]
        self.latest = (saved, dict(cursor))
        self.recovery = payload.get("recovery")

    def _load(self):
        for path in sorted(self.journal.glob("*.json")):
            record = _read(path)
            p = record["payload"]
            try:
                if (set(p) not in ({"sequence", "previous", "event", "snapshot", "cursor"},
                                  {"sequence", "previous", "event", "snapshot", "cursor", "recovery"})
                        or p["sequence"] != self._sequence + 1 or p["previous"] != self._previous
                        or path.name != f"{self._sequence + 1:012d}.json"):
                    raise ValueError("journal gap or order mismatch")
                _component(p["event"])
                snapshot = decode(Snapshot, p["snapshot"])
                if snapshot.thread_id != self.thread_id or snapshot.lease is not None:
                    raise ValueError("wrong session or persisted authority")
                self._sequence += 1
                self._previous = record["sha256"]
                self.latest = (snapshot, p["cursor"])
                self.recovery = p.get("recovery")
            except (TypeError, ValueError, KeyError) as exc:
                raise PersistenceError("invalid journal; refusing fallback to older state") from exc
        if self.latest is None:
            raise PersistenceError("missing journal; checkpoint alone cannot prove no pending request")
        snapshot, _ = self.latest
        for checkpoint in (snapshot.checkpoint, snapshot.recoverable_checkpoint):
            if checkpoint and checkpoint.commit_evidence:
                if self.read_checkpoint(checkpoint.checkpoint_id) != checkpoint:
                    raise PersistenceError("journal/checkpoint mismatch")
