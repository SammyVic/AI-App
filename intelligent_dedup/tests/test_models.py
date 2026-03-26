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
