"""Local file-backed archive contracts; no provider or Runtime acceptance claims."""

from dataclasses import replace
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from yohaku.archive import ArchiveMetadata, ArchiveTurn, ToolMetadata
from yohaku.companion import CompanionController
from yohaku.controller import TransitionError
from yohaku.model import BoundaryVerification, State, WorkspaceRevision
from yohaku.persistence import PersistenceError, _envelope, _json
from yohaku import archive, persistence


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, CODEX_HOME=self.tmp.name)
        env.start()
        self.addCleanup(env.stop)
        self.sent = []
        self.c = CompanionController("thread", self.sent.append, create=True)
        self.addCleanup(lambda: self.c.close())

    def turn(self, ident="turn-01", **changes):
        metadata = ArchiveMetadata(ident, "Token storage 調査", "research",
            ("src/TokenStore.py",), ("TokenStore", "refreshToken"), ("auth",), "completed")
        return replace(ArchiveTurn(metadata, "Inspect token storage", "COLD_ONLY_BODY",
            ("Checked existing code",), ("Keep current API",), "focused test passed",
            ("test-record-1",), (ToolMetadata("tool-1", "Bash", "completed"),)), **changes)

    def verified(self):
        c = self.c
        c.step("propose_boundary", "boundary")
        c.step("arm_barrier")
        c.step("begin_quiescence_check")
        c.step("observe_quiescence", relevant_work_remaining=False)
        workspace = WorkspaceRevision(0, "stamp", ("src/",))
        c.step("capture_workspace", workspace)
        c.step("verify_boundary", BoundaryVerification(
            0, 0, workspace, "verification_passed", "passed", "test-record", True))

    def restart(self):
        self.c.close()
        self.c = CompanionController("thread", self.sent.append)

    def test_generation_permissions_revision_and_idempotency(self):
        turn = self.turn()
        before = self.c.snapshot
        self.assertEqual(self.c.archive_turn(turn), turn.metadata)
        after = self.c.snapshot
        self.assertEqual(after.revisions.archive_revision, before.revisions.archive_revision + 1)
        self.assertEqual(after.revisions.execution_revision, before.revisions.execution_revision)
        self.assertEqual(after.state, before.state)
        self.assertEqual(self.c.read_archive("turn-01"), turn)
        self.c.archive_turn(turn)
        self.assertEqual(self.c.snapshot, after)
        for directory in (self.c.store.archives.cold, self.c.store.archives.warm):
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((directory / "turn-01.json").stat().st_mode), 0o600)
        with self.assertRaises(PersistenceError):
            self.c.archive_turn(replace(turn, assistant_final="different"))
        self.assertEqual(self.c.read_archive("turn-01"), turn)
        self.assertEqual(self.sent, [])

    def test_search_semantics_and_bounded_stable_pagination(self):
        first = self.turn()
        second = self.turn("turn-02", metadata=ArchiveMetadata(
            "turn-02", "User interface", "implementation", ("src/ui.py",),
            ("Screen",), ("ui",), "failed"))
        for turn in (second, first):
            self.c.archive_turn(turn)
        for filters in ({"path": "src/TokenStore.py"}, {"symbol": "TokenStore"},
                        {"tag": "auth"}, {"phase": "research"}, {"outcome": "completed"}):
            self.assertEqual(self.c.search_archive(**filters), (first.metadata,))
        self.assertEqual(self.c.search_archive("TOKEN 調査", tag="auth", phase="research"), (first.metadata,))
        for query, filters in (("", {"symbol": "tokenstore"}), ("", {"path": "src/"}),
                               ("", {"tag": "auth", "outcome": "failed"}), ("COLD_ONLY_BODY", {})):
            self.assertEqual(self.c.search_archive(query, **filters), ())
        self.assertEqual(self.c.search_archive(limit=1), (first.metadata,))
        self.assertEqual(self.c.search_archive(limit=1, offset=1), (second.metadata,))
        for filters in ({"limit": 0}, {"limit": 101}, {"limit": True}, {"offset": -1}, {"tag": ""}):
            with self.assertRaises(ValueError):
                self.c.search_archive(**filters)

    def test_metadata_first_reads_exactly_selected_cold_only(self):
        for ident in ("turn-01", "turn-02", "turn-03"):
            self.c.archive_turn(self.turn(ident))
        reads = []
        read = archive._read

        def traced(path):
            if path.parent.name == "archive":
                reads.append(path.name)
            return read(path)

        with patch("yohaku.archive._read", side_effect=traced):
            self.assertEqual(len(self.c.search_archive("Token")), 3)
            self.assertEqual(reads, [])
            self.c.read_archive("turn-02")
            self.assertEqual(reads, ["turn-02.json"])
        warm = (self.c.store.archives.warm / "turn-01.json").read_text()
        self.assertNotIn("COLD_ONLY_BODY", warm)
        self.assertNotIn("COLD_ONLY_BODY", "".join(p.read_text() for p in self.c.store.journal.glob("*.json")))

    def test_restart_is_metadata_only_and_reads_grant_no_authority(self):
        self.c.archive_turn(self.turn())
        with patch.object(archive.ArchiveStore, "_cold", side_effect=AssertionError("eager read")):
            self.restart()
            self.assertEqual(len(self.c.search_archive()), 1)
        before = self.c.snapshot
        self.c.read_archive("turn-01")
        self.assertEqual(self.c.snapshot, before)
        self.assertIsNone(self.c.snapshot.lease)
        self.assertEqual(self.c.snapshot.state, State.RECOVERY_REQUIRED)
        with self.assertRaises(TransitionError):
            self.c.require_work()
        self.assertEqual(self.sent, [])

    def test_fresh_process_can_search_and_read(self):
        self.c.archive_turn(self.turn())
        self.c.close()
        code = """from yohaku.companion import CompanionController
with CompanionController('thread', lambda _: (_ for _ in ()).throw(AssertionError('dispatch'))) as c:
    assert c.search_archive(symbol='TokenStore')[0].archive_id == 'turn-01'
    assert c.read_archive('turn-01').assistant_final == 'COLD_ONLY_BODY'
    assert c.snapshot.lease is None
print('PASS')
"""
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "PASS")

    def test_interrupted_index_write_stops_owner_and_rebuilds_only_missing(self):
        self.c.archive_turn(self.turn("turn-01"))
        atomic = persistence._atomic_write

        def fail_index(path, payload):
            if path.parent.name == "archive-index":
                raise OSError("injected index write interruption")
            return atomic(path, payload)

        with patch("yohaku.persistence._atomic_write", side_effect=fail_index):
            with self.assertRaises(PersistenceError):
                self.c.archive_turn(self.turn("turn-02"))
        with self.assertRaises(PersistenceError):
            self.c.require_work()
        reads = []
        read = archive._read

        def traced(path):
            if path.parent.name == "archive":
                reads.append(path.name)
            return read(path)

        with patch("yohaku.archive._read", side_effect=traced):
            self.restart()
        self.assertEqual(reads, ["turn-02.json"])
        self.assertEqual(len(self.c.search_archive()), 2)
        self.assertEqual(self.c.read_archive("turn-02"), self.turn("turn-02"))

    def test_directory_sync_failure_requires_reopen_and_temp_files_are_ignored(self):
        self.c.archive_turn(self.turn())
        sync = persistence._sync_directory

        def fail_sync(path):
            if path.name == "archive":
                raise OSError("injected post-rename failure")
            return sync(path)

        with patch("yohaku.persistence._sync_directory", side_effect=fail_sync):
            with self.assertRaises(PersistenceError):
                self.c.archive_turn(self.turn("turn-02"))
        with self.assertRaises(PersistenceError):
            self.c.step("propose_boundary", "unsafe")
        for directory in (self.c.store.archives.cold, self.c.store.archives.warm):
            (directory / ".tmp-incomplete").write_text("{")
        self.restart()
        self.assertEqual(len(self.c.search_archive()), 2)

    def test_corrupt_or_missing_archive_and_bad_index_fail_closed(self):
        self.c.archive_turn(self.turn())
        cold = self.c.store.archives.cold / "turn-01.json"
        warm = self.c.store.archives.warm / "turn-01.json"
        original_cold, original_warm = cold.read_bytes(), warm.read_bytes()
        cold.write_text("{")
        self.assertEqual(len(self.c.search_archive()), 1)  # Metadata is not body validation.
        with self.assertRaises(PersistenceError):
            self.c.read_archive("turn-01")
        cold.write_bytes(original_cold)
        payload = json.loads(original_warm)["payload"]
        payload["metadata"]["title"] = "different metadata"
        warm.write_bytes(_json(_envelope(payload)))
        with self.assertRaises(PersistenceError):
            self.c.read_archive("turn-01")
        warm.write_text("{")
        with self.assertRaises(PersistenceError):
            self.restart()
        warm.write_bytes(original_warm)
        cold.unlink()
        with self.assertRaises(PersistenceError):
            self.restart()

    def test_validation_and_symlink_rejection(self):
        self.c.archive_turn(self.turn())
        for ident in ("../escape", "/absolute", "bad.json", ""):
            with self.assertRaises(PersistenceError):
                self.c.read_archive(ident)
        with self.assertRaises(ValueError):
            self.turn(assistant_final="x" * (1024 * 1024))
        with self.assertRaises(ValueError):
            self.turn(material_policy="instructions")
        with self.assertRaises(ValueError):
            self.c.archive_turn({"reasoning": "raw provider message"})
        path = self.c.store.archives.cold / "turn-01.json"
        backup = path.with_suffix(".saved")
        path.rename(backup)
        path.symlink_to(backup)
        with self.assertRaises(PersistenceError):
            self.c.read_archive("turn-01")
        with self.assertRaises(PersistenceError):
            self.restart()

    def test_valid_checksums_do_not_allow_wrong_owner_identity_or_schema(self):
        self.c.archive_turn(self.turn())
        warm = self.c.store.archives.warm / "turn-01.json"
        original = warm.read_bytes()
        for key, value in (("thread_id", "other"), ("extra", "unexpected"),
                           ("cold_sha256", "invalid")):
            payload = json.loads(original)["payload"]
            payload[key] = value
            warm.write_bytes(_json(_envelope(payload)))
            with self.subTest(key=key), self.assertRaises(PersistenceError):
                self.c.search_archive()
        payload = json.loads(original)["payload"]
        payload["metadata"]["archive_id"] = "wrong-id"
        warm.write_bytes(_json(_envelope(payload)))
        with self.assertRaises(PersistenceError):
            self.c.search_archive()
        warm.write_bytes(original)
        cold = self.c.store.archives.cold / "turn-01.json"
        payload = json.loads(cold.read_bytes())["payload"]
        payload["thread_id"] = "other"
        cold.write_bytes(_json(_envelope(payload)))
        with self.assertRaises(PersistenceError):
            self.c.read_archive("turn-01")

    def test_checkpoint_commit_gap_preserves_archive_references(self):
        self.c.archive_turn(self.turn())
        self.verified()
        atomic = persistence._atomic_write

        def fail_commit_journal(path, payload):
            if path.parent.name == "journal" and b'"event":"checkpoint_committed"' in payload:
                raise OSError("injected checkpoint commit journal failure")
            return atomic(path, payload)

        with patch("yohaku.persistence._atomic_write", side_effect=fail_commit_journal):
            with self.assertRaises(PersistenceError):
                self.c.commit_checkpoint(archive_ids=("turn-01",))
        self.restart()
        checkpoint = self.c.snapshot.recoverable_checkpoint
        self.assertIsNotNone(checkpoint)
        self.assertEqual(self.c.store.checkpoint_archive_ids(checkpoint.checkpoint_id), ("turn-01",))
        self.assertEqual(self.c.snapshot.state, State.RECOVERY_REQUIRED)
        self.assertIsNone(self.c.snapshot.lease)

    def test_checkpoint_references_roundtrip_and_do_not_embed_cold(self):
        self.c.archive_turn(self.turn())
        self.verified()
        before = self.c.snapshot
        with self.assertRaises(PersistenceError):
            self.c.commit_checkpoint(archive_ids=("missing",))
        self.assertEqual(self.c.snapshot, before)
        checkpoint = self.c.commit_checkpoint(archive_ids=("turn-01",))
        self.assertEqual(self.c.store.checkpoint_archive_ids(checkpoint.checkpoint_id), ("turn-01",))
        self.assertNotIn("COLD_ONLY_BODY", (self.c.store.checkpoints / f"{checkpoint.checkpoint_id}.json").read_text())
        with self.assertRaises(PersistenceError):
            self.c.store.commit_checkpoint(checkpoint, archive_ids=())
        self.restart()
        self.assertEqual(self.c.snapshot.recoverable_checkpoint, checkpoint)
        self.assertEqual(self.c.store.checkpoint_archive_ids(checkpoint.checkpoint_id), ("turn-01",))

    def test_old_session_is_not_migrated_and_old_checkpoint_stays_readable(self):
        self.verified()
        checkpoint = self.c.commit_checkpoint()
        file = self.c.store.checkpoints / f"{checkpoint.checkpoint_id}.json"
        original = file.read_bytes()
        self.assertNotIn("archive_ids", json.loads(original)["payload"])
        self.restart()
        self.assertEqual(file.read_bytes(), original)
        self.assertEqual(self.c.store.checkpoint_archive_ids(checkpoint.checkpoint_id), ())
        self.assertFalse(self.c.store.archives.cold.exists())
        self.assertFalse(self.c.store.archives.warm.exists())
        self.assertEqual(self.c.search_archive(), ())


if __name__ == "__main__":
    unittest.main()
