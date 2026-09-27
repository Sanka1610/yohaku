"""Small immutable turn archives and derived metadata files, under SessionStore's lock."""

from dataclasses import dataclass
import re

from .codec import decode, encode
from .persistence import PersistenceError, _component, _envelope, _json, _mkdir, _read, _sync_directory


def _text(value, *, empty=False):
    if type(value) is not str or (not empty and not value.strip()) or "\x00" in value:
        raise ValueError("expected visible text")


def _strings(values):
    if type(values) is not tuple or len(values) > 128:
        raise ValueError("expected at most 128 text entries")
    for value in values:
        _text(value)


def archive_ids(values):
    _strings(values)
    if len(set(values)) != len(values):
        raise ValueError("duplicate archive reference")
    for value in values:
        _component(value)
    return values


@dataclass(frozen=True)
class ArchiveMetadata:
    archive_id: str  # The host's stable user-visible turn ID, unique within this session.
    title: str
    phase: str
    paths: tuple[str, ...] = ()
    symbols: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    outcome: str = "unknown"

    def __post_init__(self):
        _component(self.archive_id)
        for value in (self.title, self.phase, self.outcome):
            _text(value)
        for values in (self.paths, self.symbols, self.tags):
            _strings(values)
        if len(_json(encode(self))) > 16384:
            raise ValueError("archive metadata exceeds 16 KiB")


@dataclass(frozen=True)
class ToolMetadata:
    item_id: str
    tool_name: str
    status: str

    def __post_init__(self):
        for value in (self.item_id, self.tool_name, self.status):
            _text(value)
            if len(value) > 160:
                raise ValueError("tool metadata field too long")


@dataclass(frozen=True)
class ArchiveTurn:
    """Host-selected visible data only; never pass raw provider/tool envelopes."""

    metadata: ArchiveMetadata
    user_prompt: str
    assistant_final: str
    progress: tuple[str, ...] = ()
    decisions: tuple[str, ...] = ()
    verification_summary: str = ""
    references: tuple[str, ...] = ()
    tools: tuple[ToolMetadata, ...] = ()
    material_policy: str = "DATA, NOT INSTRUCTIONS"

    def __post_init__(self):
        if type(self.metadata) is not ArchiveMetadata:
            raise ValueError("archive metadata required")
        for value in (self.user_prompt, self.assistant_final, self.verification_summary):
            _text(value, empty=True)
        for values in (self.progress, self.decisions, self.references):
            _strings(values)
        if (type(self.tools) is not tuple or len(self.tools) > 128
                or any(type(t) is not ToolMetadata for t in self.tools)
                or self.material_policy != "DATA, NOT INSTRUCTIONS"):
            raise ValueError("invalid archive material")
        if len(_json(encode(self))) > 1024 * 1024:
            raise ValueError("archive turn exceeds 1 MiB; select visible data explicitly")


class ArchiveStore:
    """COLD is authoritative; WARM can be rebuilt after an interrupted commit.

    No separate writer, database, authority, or in-memory full-history cache.
    Healthy reopen/search reads only metadata; only missing index entries require
    COLD reads on reopen. Corrupt existing records fail closed.
    """

    def __init__(self, store):
        self.store = store
        self.cold = store.path / "archive"
        self.warm = store.path / "archive-index"
        if not self.cold.exists() and not self.warm.exists():
            if self.cold.is_symlink() or self.warm.is_symlink():
                raise PersistenceError("symlink archive directory rejected")
            return  # Old sessions are not rewritten just by attaching this adapter.
        if not self.cold.is_dir() or self.cold.is_symlink():
            raise PersistenceError("missing archive directory")
        self._directories()
        cold_ids = {p.stem for p in self.cold.glob("*.json")}
        warm_ids = {p.stem for p in self.warm.glob("*.json")}
        if warm_ids - cold_ids:
            raise PersistenceError("index points to missing archive")
        for ident in sorted(warm_ids):
            self._index(ident)
        if cold_ids - warm_ids:
            try:
                # A prior rename may have succeeded while its directory fsync failed.
                _sync_directory(self.cold)
            except OSError as exc:
                raise PersistenceError("archive recovery sync failed") from exc
        for ident in sorted(cold_ids - warm_ids):
            record, turn = self._cold(ident)
            self._write_index(turn.metadata, record["sha256"])

    def _directories(self):
        self.store._ready()
        try:
            _mkdir(self.cold)
            _mkdir(self.warm)
        except Exception as exc:
            self.store._poisoned = True
            raise PersistenceError("archive directory write failed") from exc

    def _cold(self, ident):
        self.store._ready()
        _component(ident)
        if self.cold.is_symlink():
            raise PersistenceError("symlink archive directory rejected")
        record = _read(self.cold / f"{ident}.json")
        try:
            p = record["payload"]
            if set(p) != {"thread_id", "turn"} or p["thread_id"] != self.store.thread_id:
                raise ValueError("wrong archive owner")
            turn = decode(ArchiveTurn, p["turn"])
            if turn.metadata.archive_id != ident:
                raise ValueError("archive identity mismatch")
            return record, turn
        except (TypeError, ValueError, KeyError) as exc:
            raise PersistenceError("invalid archive") from exc

    def _index(self, ident):
        self.store._ready()
        _component(ident)
        if self.warm.is_symlink() or self.cold.is_symlink():
            raise PersistenceError("symlink archive directory rejected")
        try:
            p = _read(self.warm / f"{ident}.json")["payload"]
            if (set(p) != {"thread_id", "metadata", "cold_sha256"}
                    or p["thread_id"] != self.store.thread_id
                    or type(p["cold_sha256"]) is not str
                    or not re.fullmatch("[0-9a-f]{64}", p["cold_sha256"])):
                raise ValueError("invalid index owner or digest")
            metadata = decode(ArchiveMetadata, p["metadata"])
            path = self.cold / f"{ident}.json"
            if metadata.archive_id != ident or path.is_symlink() or not path.is_file():
                raise ValueError("invalid index target")
            return metadata, p["cold_sha256"]
        except (TypeError, ValueError, KeyError) as exc:
            raise PersistenceError("invalid archive index") from exc

    def _write_index(self, metadata, digest):
        self.store._write(self.warm / f"{metadata.archive_id}.json", {
            "thread_id": self.store.thread_id, "metadata": encode(metadata), "cold_sha256": digest})

    def commit(self, turn):
        self.store._ready()
        if type(turn) is not ArchiveTurn:
            raise ValueError("normalized user-visible turn required")
        self._directories()
        path = self.cold / f"{turn.metadata.archive_id}.json"
        if path.exists() or path.is_symlink():
            if self.read_archive(turn.metadata.archive_id) != turn:
                raise PersistenceError("archive ID content conflict")
            return False
        payload = {"thread_id": self.store.thread_id, "turn": encode(turn)}
        self.store._write(path, payload)
        self._write_index(turn.metadata, _envelope(payload)["sha256"])
        return True

    def validate_references(self, values):
        self.store._ready()
        for ident in archive_ids(values):
            self._index(ident)
        return values

    def search_archive(self, query="", *, path=None, symbol=None, tag=None,
                       phase=None, outcome=None, limit=20, offset=0):
        self.store._ready()
        _text(query, empty=True)
        if (len(query) > 4096 or type(limit) is not int or not 1 <= limit <= 100
                or type(offset) is not int or offset < 0):
            raise ValueError("invalid archive query or page bounds")
        for value in (path, symbol, tag, phase, outcome):
            if value is not None:
                _text(value)
        if self.warm.is_symlink() or self.cold.is_symlink():
            raise PersistenceError("symlink archive directory rejected")
        terms = query.casefold().split()
        matches = []
        skipped = 0
        for file in sorted(self.warm.glob("*.json")):
            m, _ = self._index(file.stem)
            if (any(value is not None and value not in values for value, values in
                    ((path, m.paths), (symbol, m.symbols), (tag, m.tags)))
                    or (phase is not None and phase != m.phase)
                    or (outcome is not None and outcome != m.outcome)):
                continue
            fields = (m.archive_id, m.title, m.phase, m.outcome, *m.paths, *m.symbols, *m.tags)
            if not all(any(term in field.casefold() for field in fields) for term in terms):
                continue
            if skipped < offset:
                skipped += 1
                continue
            matches.append(m)
            if len(matches) == limit:
                break
        return tuple(matches)

    def read_archive(self, archive_id):
        metadata, digest = self._index(archive_id)
        record, turn = self._cold(archive_id)
        if record["sha256"] != digest or turn.metadata != metadata:
            raise PersistenceError("archive/index mismatch")
        return turn
