"""Task-specific observer and tools for ``document-review-report-v1``.

This module is intentionally not a general document or filesystem agent.  It
owns one fixed input set and one create-only Markdown output in a dedicated
workspace.  Runtime adapters may expose only :func:`document_review_tools` and
route the corresponding dynamic-tool requests to ``DocumentReviewTask``.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import stat

from .model import WorkspaceRevision
from .operational import OperationError, absolute, private, write_json
from .recovery import CurrentContext, ResumeProof


PROFILE = "document-review-report-v1"
READ_TOOL = "read_review_inputs"
WRITE_TOOL = "publish_review_report"
MAX_INPUTS = 16
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_REPORT_BYTES = 512 * 1024


class DocumentReviewRefusal(OperationError):
    """A fail-closed task-contract or task-observation refusal."""


def _digest_bytes(value):
    return sha256(value).hexdigest()


def _digest_file(path):
    h = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _relative(workspace, path):
    try:
        return path.relative_to(workspace).as_posix()
    except ValueError:
        raise DocumentReviewRefusal("TASK_PATH_OUTSIDE_WORKSPACE") from None


@dataclass(frozen=True)
class DocumentIdentity:
    path: str
    sha256: str
    bytes: int


@dataclass(frozen=True)
class DocumentReviewContract:
    workspace: str
    inputs: tuple[str, ...]
    output: str
    instruction: str
    logical_task_id: str
    instruction_sha256: str
    initial_inputs: tuple[DocumentIdentity, ...]

    @classmethod
    def create(cls, *, workspace, inputs, output, instruction):
        root = absolute(workspace)
        if not root.is_dir():
            raise DocumentReviewRefusal("WORKSPACE_MISSING")
        private(root, directory=True)
        if root.is_symlink():
            raise DocumentReviewRefusal("SYMLINK_PATH_REJECTED")
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 16000:
            raise DocumentReviewRefusal("TASK_INSTRUCTION_REQUIRED")
        if not isinstance(inputs, (tuple, list)) or not 1 <= len(inputs) <= MAX_INPUTS:
            raise DocumentReviewRefusal("TASK_INPUT_COUNT_OUT_OF_RANGE")
        resolved = tuple(absolute(value) for value in inputs)
        if len(set(resolved)) != len(resolved):
            raise DocumentReviewRefusal("DUPLICATE_TASK_INPUT")
        destination = absolute(output)
        if destination in resolved:
            raise DocumentReviewRefusal("OUTPUT_OVERLAPS_INPUT")
        names = tuple(_relative(root, path) for path in resolved)
        out_name = _relative(root, destination)
        identities = []
        total = 0
        for name, path in zip(names, resolved, strict=True):
            try:
                info = path.stat(follow_symlinks=False)
            except FileNotFoundError:
                raise DocumentReviewRefusal("TASK_INPUT_MISSING") from None
            if path.is_symlink() or not stat.S_ISREG(info.st_mode):
                raise DocumentReviewRefusal("TASK_INPUT_MUST_BE_REGULAR")
            private(path)
            if info.st_size > MAX_INPUT_BYTES:
                raise DocumentReviewRefusal("TASK_INPUT_TOO_LARGE")
            total += info.st_size
            if total > MAX_INPUT_BYTES:
                raise DocumentReviewRefusal("TASK_INPUTS_TOO_LARGE")
            identities.append(DocumentIdentity(name, _digest_file(path), info.st_size))
        if destination.exists() or destination.is_symlink():
            raise DocumentReviewRefusal("STALE_OUTPUT_PRESENT")
        if destination.parent != root and not destination.parent.is_dir():
            raise DocumentReviewRefusal("OUTPUT_PARENT_MISSING")
        for part in (destination.parent, *destination.parent.parents):
            if part == root.parent:
                break
            if part.is_symlink():
                raise DocumentReviewRefusal("SYMLINK_PATH_REJECTED")
        declared = set(names)
        actual = set()
        for path in root.rglob("*"):
            if path.is_symlink():
                raise DocumentReviewRefusal("SYMLINK_PATH_REJECTED")
            if path.is_file():
                actual.add(path.relative_to(root).as_posix())
        if actual != declared:
            raise DocumentReviewRefusal("DEDICATED_WORKSPACE_CONTAINS_UNDECLARED_FILES")
        instruction_hash = _digest_bytes(instruction.encode())
        binding = json.dumps({
            "profile": PROFILE,
            "workspace": str(root),
            "inputs": [asdict(item) for item in identities],
            "output": out_name,
            "instruction_sha256": instruction_hash,
        }, sort_keys=True, separators=(",", ":")).encode()
        return cls(str(root), tuple(str(path) for path in resolved), str(destination),
                   instruction, "document-review-" + _digest_bytes(binding)[:24],
                   instruction_hash, tuple(identities))

    @property
    def relevant_scope(self):
        return tuple(item.path for item in self.initial_inputs) + (_relative(
            Path(self.workspace), Path(self.output)),)


@dataclass(frozen=True)
class DocumentReviewObservation:
    logical_task_id: str
    instruction_sha256: str
    inputs: tuple[DocumentIdentity, ...]
    output_exists: bool
    output_sha256: str | None
    read_complete: bool
    read_count: int
    write_started: bool
    write_completed: bool
    result_incorporated: bool
    active_work: tuple[str, ...]
    pending_work: tuple[str, ...]
    workspace: WorkspaceRevision


def document_review_tools():
    return [
        {"type": "function", "name": READ_TOOL,
         "description": ("Read the complete, host-declared input set for the current "
                         "document-review-report-v1 task. Takes no arguments. Do not use "
                         "shell or filesystem tools."),
         "inputSchema": {"type": "object", "properties": {},
                         "additionalProperties": False}},
        {"type": "function", "name": WRITE_TOOL,
         "description": ("Create the one fixed Markdown review report exactly once. Call only "
                         "after a fresh post-transition read. The host adds provenance metadata."),
         "inputSchema": {"type": "object", "properties": {
             "markdown": {"type": "string", "minLength": 1, "maxLength": MAX_REPORT_BYTES}},
             "required": ["markdown"], "additionalProperties": False}},
    ]


class DocumentReviewTask:
    """Trusted task observer, exact tool executor and mechanical assessor."""

    def __init__(self, contract, state_dir):
        if not isinstance(contract, DocumentReviewContract):
            raise TypeError("DocumentReviewContract required")
        self.contract = contract
        self.state_dir = absolute(state_dir)
        private(self.state_dir, directory=True)
        self.state_path = self.state_dir / "document-review-task.json"
        if self.state_path.exists():
            raise DocumentReviewRefusal("TASK_STATE_ALREADY_EXISTS")
        self.phase = "INITIAL_READ"
        self.read_count = 0
        self.read_hashes = []
        self.write_started = False
        self.write_completed = False
        self.write_hash = None
        self.result_incorporated = False
        self.active = {}
        self.pending = {}
        self.incorporated = []
        self.events = []
        self.refusal = None
        self._epoch = 0
        self._save("task_initialized")

    def _save(self, event):
        self.events.append(event)
        value = {
            "schema": 1, "profile": PROFILE, "logical_task_id": self.contract.logical_task_id,
            "instruction_sha256": self.contract.instruction_sha256,
            "initial_inputs": [asdict(item) for item in self.contract.initial_inputs],
            "output": _relative(Path(self.contract.workspace), Path(self.contract.output)),
            "phase": self.phase, "read_count": self.read_count,
            "read_hashes": self.read_hashes, "write_started": self.write_started,
            "write_completed": self.write_completed, "write_hash": self.write_hash,
            "result_incorporated": self.result_incorporated,
            "active": self.active, "pending": self.pending,
            "incorporated": self.incorporated, "events": self.events,
            "refusal": self.refusal, "mutation_epoch": self._epoch,
        }
        write_json(self.state_path, value, create=not self.state_path.exists())

    def _refuse(self, reason):
        self.refusal = reason
        self.phase = "AMBIGUOUS"
        self._save("refused:" + reason)
        raise DocumentReviewRefusal(reason)

    def _current_inputs(self):
        values = []
        for initial, raw in zip(self.contract.initial_inputs, self.contract.inputs, strict=True):
            path = Path(raw)
            try:
                info = path.stat(follow_symlinks=False)
                private(path)
            except (FileNotFoundError, OperationError):
                self._refuse("INPUT_REVISION_CHANGED")
            if path.is_symlink() or not stat.S_ISREG(info.st_mode):
                self._refuse("INPUT_REVISION_CHANGED")
            values.append(DocumentIdentity(initial.path, _digest_file(path), info.st_size))
        return tuple(values)

    def _workspace_files(self):
        root = Path(self.contract.workspace)
        try:
            private(root, directory=True)
        except OperationError:
            self._refuse("WORKSPACE_PRIVACY_CHANGED")
        values = set()
        for path in root.rglob("*"):
            if path.is_symlink():
                self._refuse("WORKSPACE_SYMLINK_DETECTED")
            if path.is_file():
                values.add(path.relative_to(root).as_posix())
        return values

    def observe(self):
        current = self._current_inputs()
        output = Path(self.contract.output)
        output_exists = output.exists()
        if output.is_symlink() or (output_exists and not output.is_file()):
            self._refuse("INVALID_OUTPUT_OBJECT")
        allowed = {item.path for item in current}
        if output_exists:
            allowed.add(_relative(Path(self.contract.workspace), output))
        if self._workspace_files() != allowed:
            self._refuse("UNDECLARED_WORKSPACE_FILE")
        output_hash = _digest_file(output) if output_exists else None
        material = json.dumps({
            "instruction_sha256": self.contract.instruction_sha256,
            "inputs": [asdict(item) for item in current],
            "output": {"exists": output_exists, "sha256": output_hash},
        }, sort_keys=True, separators=(",", ":")).encode()
        workspace = WorkspaceRevision(self._epoch, _digest_bytes(material),
                                      self.contract.relevant_scope)
        return DocumentReviewObservation(
            self.contract.logical_task_id, self.contract.instruction_sha256, current,
            output_exists, output_hash, self.read_count > 0, self.read_count,
            self.write_started, self.write_completed, self.result_incorporated,
            tuple(self.active), tuple(self.pending), workspace)

    def current_context(self):
        value = self.observe()
        return CurrentContext(value.logical_task_id, 0, self._epoch, value.workspace)

    def begin_continuation(self):
        value = self.observe()
        if (self.phase != "INITIAL_READ_DONE" or self.read_count != 1
                or value.inputs != self.contract.initial_inputs or value.output_exists
                or value.active_work or value.pending_work):
            self._refuse("TRANSITION_BOUNDARY_NOT_READY")
        self.phase = "CONTINUATION"
        self._save("continuation_enabled")

    def handle_call(self, message):
        params = message.get("params", {})
        call = params.get("callId")
        tool = params.get("tool")
        args = params.get("arguments")
        if ("id" not in message or not isinstance(call, str) or not call
                or params.get("namespace") is not None or call in self.active
                or call in self.pending or call in self.incorporated):
            self._refuse("INVALID_OR_REPLAYED_TOOL_CALL")
        if tool not in (READ_TOOL, WRITE_TOOL):
            self._refuse("UNRELATED_TOOL_REFUSED")
        self.active[call] = tool
        self._save("tool_active:" + tool)
        try:
            if tool == READ_TOOL:
                payload = self._read(args)
            else:
                payload = self._write(args)
        except DocumentReviewRefusal:
            raise
        except Exception:
            self._refuse("TOOL_RESULT_UNKNOWN")
        self.active.pop(call)
        self.pending[call] = tool
        self._save("tool_result_pending:" + tool)
        return {"id": message["id"], "result": {"success": True,
            "contentItems": [{"type": "inputText", "text": json.dumps(
                payload, ensure_ascii=False, sort_keys=True)}]}}

    def _read(self, args):
        if args != {}:
            self._refuse("READ_ARGUMENTS_REFUSED")
        if self.phase not in ("INITIAL_READ", "CONTINUATION"):
            self._refuse("READ_NOT_PENDING")
        expected = 0 if self.phase == "INITIAL_READ" else 1
        if self.read_count != expected:
            self._refuse("READ_ALREADY_COMPLETED")
        current = self.observe()
        if current.inputs != self.contract.initial_inputs:
            self._refuse("INPUT_REVISION_CHANGED")
        if current.output_exists:
            self._refuse("STALE_OUTPUT_PRESENT")
        documents = []
        for identity, raw in zip(current.inputs, self.contract.inputs, strict=True):
            try:
                text = Path(raw).read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                self._refuse("INPUT_READ_FAILED")
            documents.append({"identity": asdict(identity), "content": text})
        self.read_count += 1
        self.read_hashes.append([asdict(item) for item in current.inputs])
        self.phase = "INITIAL_READ_PENDING" if self.read_count == 1 else "FRESH_READ_PENDING"
        self._save("read_completed")
        return {"profile": PROFILE, "instruction": self.contract.instruction,
                "instruction_sha256": self.contract.instruction_sha256,
                "documents": documents, "output": _relative(
                    Path(self.contract.workspace), Path(self.contract.output)),
                "quality_verdict": "NOT_ASSESSED"}

    def _write(self, args):
        if self.phase != "FRESH_READ_DONE" or self.read_count != 2:
            self._refuse("WRITE_NOT_PENDING")
        if (not isinstance(args, dict) or set(args) != {"markdown"}
                or not isinstance(args["markdown"], str)):
            self._refuse("INVALID_REPORT_ARGUMENTS")
        body = args["markdown"].strip()
        if not body.startswith("#") or len(body.encode()) > MAX_REPORT_BYTES:
            self._refuse("INVALID_MARKDOWN_REPORT")
        current = self.observe()
        if current.inputs != self.contract.initial_inputs:
            self._refuse("INPUT_REVISION_CHANGED")
        if current.output_exists or self.write_started:
            self._refuse("COMPLETED_OR_STALE_WRITE_REFUSED")
        metadata = {
            "profile": PROFILE,
            "logical_task_id": self.contract.logical_task_id,
            "instruction_sha256": self.contract.instruction_sha256,
            "inputs": [asdict(item) for item in current.inputs],
            "quality_verdict": "NOT_ASSESSED",
        }
        report = ("<!-- yohaku-task-provenance "
                  + json.dumps(metadata, ensure_ascii=False, sort_keys=True)
                  + " -->\n\n" + body + "\n").encode()
        self.write_started = True
        self._epoch += 1
        self._save("write_started")
        path = Path(self.contract.output)
        try:
            self._publish_bytes(path, report)
        except Exception:
            self._refuse("WRITE_RESULT_UNKNOWN_NO_RETRY")
        self.write_completed = True
        self.write_hash = _digest_file(path)
        if self.write_hash != _digest_bytes(report):
            self._refuse("WRITE_READBACK_MISMATCH_NO_RETRY")
        self.phase = "WRITE_PENDING"
        self._save("write_completed")
        return {"profile": PROFILE, "output": _relative(Path(self.contract.workspace), path),
                "sha256": self.write_hash, "bytes": len(report),
                "quality_verdict": "NOT_ASSESSED"}

    @staticmethod
    def _publish_bytes(path, report):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(report)
            stream.flush()
            os.fsync(stream.fileno())
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def incorporate(self, item):
        if not isinstance(item, dict) or item.get("type") != "dynamicToolCall":
            return False
        ident = item.get("id")
        tool = item.get("tool")
        matches = [(call, name) for call, name in self.pending.items() if name == tool]
        if (not isinstance(ident, str) or not ident or len(matches) != 1
                or item.get("status") != "completed" or item.get("success") is not True):
            self._refuse("TOOL_RESULT_NOT_INCORPORATED")
        call, _ = matches[0]
        self.pending.pop(call)
        self.incorporated.append(ident)
        if tool == READ_TOOL:
            if self.phase == "INITIAL_READ_PENDING":
                self.phase = "INITIAL_READ_DONE"
            elif self.phase == "FRESH_READ_PENDING":
                self.phase = "FRESH_READ_DONE"
            else:
                self._refuse("STALE_READ_RESULT")
        elif tool == WRITE_TOOL:
            if self.phase != "WRITE_PENDING" or not self.write_completed:
                self._refuse("STALE_WRITE_RESULT")
            self.result_incorporated = True
            self.phase = "COMPLETE"
        self._save("tool_result_incorporated:" + tool)
        return True

    def assessor(self, document, tools):
        current = self.current_context()
        dynamic = [item for item in tools if item.get("type") == "dynamicToolCall"]
        unrelated = [item for item in tools if item.get("type") != "dynamicToolCall"]
        reads = [item for item in dynamic if item.get("tool") == READ_TOOL]
        writes = [item for item in dynamic if item.get("tool") == WRITE_TOOL]
        successful = lambda item: (item.get("status") == "completed"
                                   and item.get("success") is True)
        observation = self.observe()
        refs = set(document.recovered.workspace_references)
        expected_refs = {"profile=" + PROFILE,
                         "instruction_sha256=" + self.contract.instruction_sha256,
                         *{"input=" + item.path + ":" + item.sha256
                           for item in self.contract.initial_inputs}}
        valid = (
            not unrelated and len(reads) == 1 and len(writes) == 1
            and all(successful(item) for item in (*reads, *writes))
            and self.phase == "COMPLETE" and self.read_count == 2
            and self.write_started and self.write_completed and self.result_incorporated
            and observation.inputs == self.contract.initial_inputs
            and observation.output_exists and observation.output_sha256 == self.write_hash
            and not observation.active_work and not observation.pending_work
            and expected_refs <= refs
            and document.recovered.logical_task_id == self.contract.logical_task_id
            and document.recovered.next_action_candidate == "fresh read, then publish the one report"
            and self.events.count("write_started") == 1
            and self.events.count("write_completed") == 1
            and len([event for event in self.events
                     if event == "tool_result_incorporated:" + READ_TOOL]) == 2
            and len(self.events) - 1 - self.events[::-1].index(
                "tool_result_incorporated:" + READ_TOOL)
                < self.events.index("write_started")
                < self.events.index("tool_result_incorporated:" + WRITE_TOOL)
        )
        if not valid:
            self._refuse("TASK_ASSESSMENT_FAILED")
        evidence = _digest_bytes(json.dumps({
            "logical_task_id": current.logical_task_id,
            "workspace_stamp": current.workspace.workspace_stamp,
            "output_sha256": observation.output_sha256,
            "read_item": reads[0]["id"], "write_item": writes[0]["id"],
        }, sort_keys=True).encode())
        return ResumeProof(current, "document-review-assessment:" + evidence,
                           (reads[0]["id"],), (writes[0]["id"],),
                           True, True, True, True, True)

    def result(self):
        value = self.observe()
        return {
            "profile": PROFILE,
            "logical_task_id": self.contract.logical_task_id,
            "mechanical_task_completion": "PASS" if self.phase == "COMPLETE" else "AMBIGUOUS",
            "writing_quality": "NOT_ASSESSED",
            "input_documents": [asdict(item) for item in value.inputs],
            "instruction_sha256": value.instruction_sha256,
            "output": {"path": _relative(Path(self.contract.workspace), Path(self.contract.output)),
                       "exists": value.output_exists, "sha256": value.output_sha256},
            "read_complete": value.read_complete,
            "read_count": value.read_count,
            "write_started": value.write_started,
            "write_completed": value.write_completed,
            "result_incorporated": value.result_incorporated,
            "active_work": list(value.active_work),
            "pending_work": list(value.pending_work),
            "workspace_revision": asdict(value.workspace),
            "events": list(self.events),
            "refusal": self.refusal,
        }
