"""
tests/test_database_impact.py
=============================================================================
Direct tests for ScanRepository to hit corner cases and error paths.
=============================================================================
"""
import pytest
import sqlite3
import os
import json
from app.models.database import init_db, ScanSession, DuplicateGroup, FileAction

from app.models.repository import ScanRepository

def test_repository_get_lifetime_stats_empty(tmp_path):
    """This test case verifies that the ScanRepository correctly reports zero values for lifetime statistics when the database is freshly initialized and contains no recorded scan sessions or file deletion actions."""
    db_file = str(tmp_path / "test.db")
    SessionLocal = init_db(db_file)

    with SessionLocal() as sess:
        repo = ScanRepository(sess)
        stats = repo.get_lifetime_stats()
        assert stats["total_files_deleted"] == 0
        assert stats["total_space_freed_bytes"] == 0

def test_repository_update_group_agent_decision(tmp_path):
    """This functional test validates that the repository can successfully persist an AI agent's recommendation for a duplicate group, including the specific file to keep and the associated confidence score for analysis."""
    db_file = str(tmp_path / "test_ua.db")
    SessionLocal = init_db(db_file)
    with SessionLocal() as sess:
        repo = ScanRepository(sess)
        s = repo.create_session("path", "hash")
        g = repo.create_group(s.id, "key1", "match", ["p1"], 100)
        sess.commit() # Ensure g gets an ID and is persistent
        repo.update_group_agent_decision(g.id, "p1", 0.95, [{"reasoning": "test"}])
        
        # Verify
        sess.refresh(g)
        assert g.agent_recommended_keep == "p1"
        assert g.agent_confidence == 0.95

def test_repository_list_sessions_paging(tmp_path):
    """This test ensures that the session listing functionality correctly implements limit-based paging and provides results in descending chronological order, allowing the user interface to efficiently display recent scan history data."""
    db_file = str(tmp_path / "test_paging.db")
    SessionLocal = init_db(db_file)
    with SessionLocal() as sess:
        repo = ScanRepository(sess)
        for i in range(10):
            s = repo.create_session(f"path{i}", "hash")
            repo.complete_session(s.id, 10, 1, 1, 100) # Must be completed to show in list
        
        results = repo.list_sessions(limit=5)
        assert len(results) == 5
        assert results[0].folder_path == "path9" # Latest first

def test_repository_log_action_error(tmp_path):
    """This test case confirms the robustness of the action logging system by verifying that it gracefully handles operation logging even when provided with minimal data, ensuring comprehensive audit trail persistence always."""
    # Test logging action without enough data
    db_file = str(tmp_path / "test_log.db")
    SessionLocal = init_db(db_file)
    with SessionLocal() as sess:
        repo = ScanRepository(sess)
        # Should not raise unless unique constraint etc
        repo.log_action("path", "deleted", 100)
        logs = sess.query(FileAction).all()
        assert len(logs) == 1

