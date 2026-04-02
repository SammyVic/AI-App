"""
=============================================================================
tests/test_models.py
=============================================================================
Unit tests for the SQLAlchemy data layer.
=============================================================================
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, ScanSession, FileMetadata, DuplicateGroup, FileAction
from app.models.repository import ScanRepository
from app.engine.scanner import ScanConfig, FileInfo, SYSTEM_EXCLUSIONS
from app.engine.deduplicator import Deduplicator
from unittest.mock import patch, MagicMock


@pytest.fixture
def db_session():
    """In-memory SQLite for isolated tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    sess = SessionLocal()
    yield sess
    sess.close()


@pytest.fixture
def repo(db_session):
    return ScanRepository(db_session)


class TestScanSession:
    def test_create_session(self, repo):
        sess = repo.create_session(folder_path="C:/test", comparison_method="sha256")
        assert sess.id is not None
        assert sess.status == "running"
        assert sess.folder_path == "C:/test"

    def test_complete_session(self, repo):
        sess = repo.create_session("C:/test")
        updated = repo.complete_session(sess.id, 100, 5, 10, 1024 * 1024)
        assert updated.status == "completed"
        assert updated.files_scanned == 100
        assert updated.duplicate_groups == 5

    def test_fail_session(self, repo):
        sess = repo.create_session("C:/test")
        repo.fail_session(sess.id, "disk error")
        loaded = repo.get_session(sess.id)
        assert loaded.status == "error"
        assert "disk error" in loaded.error_message

    def test_list_sessions_only_completed(self, repo):
        s1 = repo.create_session("C:/a")
        repo.complete_session(s1.id, 10, 1, 2, 0)
        s2 = repo.create_session("C:/b")  # still running
        sessions = repo.list_sessions()
        assert any(s.id == s1.id for s in sessions)
        assert not any(s.id == s2.id for s in sessions)

    def test_cancel_session(self, repo):
        sess = repo.create_session("C:/test")
        repo.cancel_session(sess.id)
        updated = repo.get_session(sess.id)
        assert updated.status == "cancelled"
        assert updated.completed_at is not None

    def test_get_sessions_in_range(self, repo):
        # Create a session in the past
        sess = repo.create_session("C:/old")
        from datetime import datetime, timezone, timedelta
        sess.started_at = (datetime.now(timezone.utc) - timedelta(days=5)).timestamp()
        repo.complete_session(sess.id, 10, 1, 1, 100)
        
        # Create a session now
        now_sess = repo.create_session("C:/now")
        repo.complete_session(now_sess.id, 20, 2, 2, 200)

        # Query range
        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc) + timedelta(days=1)
        results = repo.get_sessions_in_range(start_date, end_date)
        
        assert len(results) == 1
        assert results[0].id == now_sess.id

    def test_get_latest_session_empty(self, repo):
        assert repo.get_latest_session() is None

    def test_update_session_state(self, repo):
        sess = repo.create_session("C:/test")
        state = {"checked": ["a.txt"], "deleted": ["b.txt"]}
        repo.update_session_state(sess.id, state)
        
        loaded = repo.get_session(sess.id)
        import json
        assert json.loads(loaded.user_state_json) == state

    def test_fail_non_existent_session(self, repo):
        # Should not raise
        repo.fail_session(999, "error")

    def test_complete_non_existent_session(self, repo):
        res = repo.complete_session(999, 0, 0, 0, 0)
        assert res is None

    def test_cancel_non_existent_session(self, repo):
        # Should not raise
        repo.cancel_session(999)

    def test_list_sessions_limit(self, repo):
        for i in range(10):
            s = repo.create_session(f"C:/{i}")
            repo.complete_session(s.id, 1, 1, 1, 1)
        
        sessions = repo.list_sessions(limit=5)
        assert len(sessions) == 5

    def test_started_at_human(self, repo):
        sess = repo.create_session("C:/test")
        # Just check it returns a string and doesn't crash
        human = sess.started_at_human()
        assert isinstance(human, str)
        assert len(human) > 10


class TestDuplicateGroup:
    def test_create_group(self, repo):
        sess = repo.create_session("C:/test")
        grp = repo.create_group(
            session_id=sess.id,
            group_key="exact_0",
            match_type="exact_hash",
            file_paths=["C:/a.txt", "C:/b.txt"],
            space_recoverable_bytes=1024,
        )
        repo._session.commit()
        assert grp.id is not None
        assert grp.file_paths == ["C:/a.txt", "C:/b.txt"]

    def test_get_groups_for_session(self, repo):
        sess = repo.create_session("C:/test")
        repo.create_group(sess.id, "exact_0", "exact_hash", ["a", "b"])
        repo.create_group(sess.id, "fuzzy_1", "fuzzy", ["c", "d"])
        repo._session.commit()
        groups = repo.get_groups_for_session(sess.id)
        assert len(groups) == 2

    def test_update_agent_decision(self, repo):
        sess = repo.create_session("C:/test")
        grp = repo.create_group(sess.id, "k", "t", ["p"])
        repo._session.commit()
        
        repo.update_group_agent_decision(
            grp.id, 
            recommended_keep="p", 
            confidence=0.95, 
            reasoning=[{"text": "high similarity"}]
        )
        
        updated = repo._session.get(grp.__class__, grp.id)
        assert updated.agent_recommended_keep == "p"
        assert updated.agent_confidence == 0.95
        import json
        assert json.loads(updated.agent_reasoning_json) == [{"text": "high similarity"}]


class TestFileMetadata:
    def test_add_and_bulk_add(self, repo):
        sess = repo.create_session("C:/test")
        # Single add
        fm = repo.add_file_metadata(sess.id, "C:/a.txt", "a.txt", ".txt", 100, 1234.5)
        repo._session.commit()
        assert fm.id is not None
        
        # Bulk add
        from app.models.database import FileMetadata
        fms = [
            FileMetadata(session_id=sess.id, full_path="C:/b.txt", filename="b.txt", extension=".txt", size_bytes=200, modified_at=1235.0),
            FileMetadata(session_id=sess.id, full_path="C:/c.txt", filename="c.txt", extension=".txt", size_bytes=300, modified_at=1236.0),
        ]
        repo.bulk_add_files(fms)
        
        # Verify
        from sqlalchemy import select
        all_files = repo._session.execute(select(FileMetadata)).scalars().all()
        assert len(all_files) == 3

    def test_update_file_hash(self, repo):
        sess = repo.create_session("C:/test")
        fm = repo.add_file_metadata(sess.id, "C:/a.txt", "a.txt", ".txt", 100, 1234.5)
        repo._session.commit()
        
        repo.update_file_hash(fm.id, md5="abc", sha256="def")
        
        updated = repo._session.get(fm.__class__, fm.id)
        assert updated.md5_hash == "abc"
        assert updated.sha256_hash == "def"

    def test_update_non_existent_file_hash(self, repo):
        # Should not raise
        repo.update_file_hash(999, md5="abc")


class TestFileAction:
    def test_log_action(self, repo):
        action = repo.log_action("C:/test.txt", "deleted", freed_bytes=2048)
        assert action.id is not None
        assert action.action == "deleted"
        assert action.freed_bytes == 2048


class TestLifetimeStats:
    def test_empty_stats(self, repo):
        stats = repo.get_lifetime_stats()
        assert stats["total_runs"] == 0
        assert stats["total_space_freed_bytes"] == 0

    def test_stats_after_completion(self, repo):
        s = repo.create_session("C:/x")
        repo.complete_session(s.id, 50, 3, 6, 2_000_000)
        repo.log_action("C:/a.txt", "deleted", freed_bytes=500_000)
        stats = repo.get_lifetime_stats()
        assert stats["total_runs"] == 1
        assert stats["total_files_scanned"] == 50
        assert stats["total_space_freed_bytes"] == 500_000

    def test_get_space_saved_in_range(self, repo):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        
        # Action today
        repo.log_action("C:/today.txt", "deleted", freed_bytes=1000)
        
        # Action yesterday
        yesterday = now - timedelta(days=1)
        fa = repo.log_action("C:/old.txt", "deleted", freed_bytes=500)
        fa.acted_at = yesterday.timestamp()
        repo._session.commit()
        
        # Query range for today only
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)
        saved = repo.get_space_saved_in_range(start, end)
        assert saved == 1000
        
        # Query range including yesterday
        start_far = now - timedelta(days=2)
        saved_all = repo.get_space_saved_in_range(start_far, end)
        assert saved_all == 1500

    def test_stats_with_no_completed_runs(self, repo):
        # create a running session
        repo.create_session("C:/running")
        # stats should still be zero for completed fields
        stats = repo.get_lifetime_stats()
        assert stats["total_runs"] == 0
        assert stats["total_files_scanned"] == 0


class TestEngineBasics:
    def test_file_info_properties(self):
        fi = FileInfo("C:/test/sub/file.txt", 100, ".txt", 0)
        assert fi.filename == "file.txt"
        # normalize path for windows/linux compatibility in tests if possible
        import os
        assert os.path.normpath(fi.directory) == os.path.normpath("C:/test/sub")

    def test_system_exclusions(self):
        assert "windows" in SYSTEM_EXCLUSIONS
        assert ".git" in SYSTEM_EXCLUSIONS

    def test_deduplicator_simple_match(self):
        config = ScanConfig(start_dir="C:/test", allowed_extensions={".txt"})
        
        # files to return from mock scanner
        mock_files = [
            FileInfo("C:/test/a.txt", 100, ".txt", 0),
            FileInfo("C:/test/copy/a.txt", 100, ".txt", 0), # Same name & same size (bucketed by size first)
            FileInfo("C:/test/b.txt", 200, ".txt", 0),      # Unique size
        ]

        with patch("app.engine.deduplicator.FileScanner") as MockScanner:
            scanner_inst = MockScanner.return_value
            scanner_inst.scan.return_value = mock_files
            
            # Use 'simple' which is name + size
            deduper = Deduplicator(config, algorithm="simple")
            result = deduper.run()
            
            assert result.files_scanned == 3
            assert len(result.groups) == 1
            assert result.groups[0].match_type == "simple"
            assert result.groups[0].group_size == 2
            assert result.space_recoverable_bytes == 100

    def test_deduplicator_cancel(self):
        config = ScanConfig(start_dir="C:/test", allowed_extensions={".txt"})
        
        mock_files = [FileInfo(f"C:/{i}.txt", 100, ".txt", 0) for i in range(100)]

        with patch("app.engine.deduplicator.FileScanner") as MockScanner:
            scanner_inst = MockScanner.return_value
            scanner_inst.scan.return_value = mock_files
            
            # We'll cancel it during the scan pass
            # The Deduplicator checks is_cancelled in the loop
            cancelled = [False]
            
            def progress_cb(pass_num, done, total, dupes, eta):
                if done > 10:
                    cancelled[0] = True
            
            deduper = Deduplicator(config, cancelled_flag=cancelled, on_progress=progress_cb)
            result = deduper.run()
            
            # It should stop fairly early
            assert result.files_scanned < 100
            assert result.passes_completed == 1

    def test_deduplicator_fuzzy_match(self):
        config = ScanConfig(start_dir="C:/test", allowed_extensions={".txt"})
        
        # Files with very similar names (>0.85 ratio)
        mock_files = [
            FileInfo("C:/test/Report_2023.txt", 100, ".txt", 0),
            FileInfo("C:/test/Report 2023.txt", 100, ".txt", 0),
            FileInfo("C:/test/unrelated.txt", 100, ".txt", 0),
        ]

        with patch("app.engine.deduplicator.FileScanner") as MockScanner:
            scanner_inst = MockScanner.return_value
            scanner_inst.scan.return_value = mock_files
            
            # algorithm='sha' but use_fuzzy=True
            # Since the sizes are same (100) and hashes will be same (default mock)
            # wait, if I don't mock hashes, they might both get 'None' or something.
            # Actually, Deduplicator uses FileHasher. Let's mock FileHasher too.
            
            with patch("app.engine.deduplicator.FileHasher") as MockHasher:
                hasher_inst = MockHasher.return_value
                # Return different hashes so they DON'T match in Pass 2
                hasher_inst.hash_batch.return_value = {
                    "C:/test/file_v1.txt": "hash1",
                    "C:/test/file_v1_fixed.txt": "hash2",
                    "C:/test/unrelated.txt": "hash3",
                }
                
                deduper = Deduplicator(config, use_fuzzy=True)
                result = deduper.run()
                
                # Should find 1 group with 2 files via fuzzy pass
                fuzzy_groups = [g for g in result.groups if g.match_type == "fuzzy"]
                assert len(fuzzy_groups) == 1
                assert len(fuzzy_groups[0].file_paths) == 2
