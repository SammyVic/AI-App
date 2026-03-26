"""
=============================================================================
app/models/repository.py
=============================================================================
Data Access Layer (DAL) — typed CRUD operations on top of SQLAlchemy models.

All writes are transactional. Callers should treat the SessionLocal as a
context manager for automatic rollback on exceptions.
=============================================================================
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Sequence

from sqlalchemy.orm import Session
from sqlalchemy import func, select

from app.models.database import (
    ScanSession, FileMetadata, DuplicateGroup, FileAction,
)

logger = logging.getLogger(__name__)


class ScanRepository:
    """
    Repository providing all database operations for the duplicate finder.
    Accepts a SQLAlchemy Session at construction time for full testability.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # ScanSession CRUD
    # ------------------------------------------------------------------

    def create_session(
        self,
        folder_path: str,
        comparison_method: str = "sha256",
        used_semantic: bool = False,
        used_fuzzy: bool = False,
        used_phash: bool = False,
    ) -> ScanSession:
        """
        Open a new scan session (status='running').
        Should be called before scanning begins.
        """
        sess = ScanSession(
            folder_path=folder_path,
            comparison_method=comparison_method,
            used_semantic=used_semantic,
            used_fuzzy=used_fuzzy,
            used_phash=used_phash,
            started_at=datetime.now(timezone.utc).timestamp(),
            status="running",
        )
        self._session.add(sess)
        self._session.commit()
        logger.info("Created ScanSession id=%d for %r", sess.id, folder_path)
        return sess

    def complete_session(
        self,
        session_id: int,
        files_scanned: int,
        duplicate_groups: int,
        duplicate_files: int,
        space_recoverable_bytes: int,
    ) -> Optional[ScanSession]:
        """Mark a scan session as completed and record final metrics."""
        sess = self._session.get(ScanSession, session_id)
        if not sess:
            logger.warning("complete_session: session id=%d not found", session_id)
            return None
        now = datetime.now(timezone.utc).timestamp()
        sess.completed_at = now
        sess.duration_seconds = now - sess.started_at
        sess.files_scanned = files_scanned
        sess.duplicate_groups = duplicate_groups
        sess.duplicate_files = duplicate_files
        sess.space_recoverable_bytes = space_recoverable_bytes
        sess.status = "completed"
        self._session.commit()
        return sess

    def fail_session(self, session_id: int, error: str) -> None:
        """Mark a session as failed with an error message."""
        sess = self._session.get(ScanSession, session_id)
        if sess:
            sess.status = "error"
            sess.error_message = error[:4096]
            sess.completed_at = datetime.now(timezone.utc).timestamp()
            self._session.commit()

    def cancel_session(self, session_id: int) -> None:
        """Mark session as cancelled (user pressed Cancel)."""
        sess = self._session.get(ScanSession, session_id)
        if sess:
            sess.status = "cancelled"
            sess.completed_at = datetime.now(timezone.utc).timestamp()
            self._session.commit()

    def get_session(self, session_id: int) -> Optional[ScanSession]:
        return self._session.get(ScanSession, session_id)

    def list_sessions(self, limit: int = 50) -> list[ScanSession]:
        """Return most recent N completed sessions."""
        return (
            self._session.execute(
                select(ScanSession)
                .where(ScanSession.status == "completed")
                .order_by(ScanSession.started_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    def get_sessions_in_range(
        self, start: datetime, end: datetime
    ) -> list[ScanSession]:
        """Return sessions whose scan started between start and end (UTC)."""
        return (
            self._session.execute(
                select(ScanSession)
                .where(
                    ScanSession.started_at >= start.timestamp(),
                    ScanSession.started_at <= end.timestamp(),
                    ScanSession.status == "completed",
                )
                .order_by(ScanSession.started_at.desc())
            )
            .scalars()
            .all()
        )

    # ------------------------------------------------------------------
    # FileMetadata CRUD
    # ------------------------------------------------------------------

    def add_file_metadata(
        self,
        session_id: int,
        full_path: str,
        filename: str,
        extension: str,
        size_bytes: int,
        modified_at: float,
        is_symlink: bool = False,
    ) -> FileMetadata:
        """Insert a single file record. Hashes populated later by hasher."""
        fm = FileMetadata(
            session_id=session_id,
            full_path=full_path,
            filename=filename,
            extension=extension,
            size_bytes=size_bytes,
            modified_at=modified_at,
            is_symlink=is_symlink,
        )
        self._session.add(fm)
        return fm  # caller should commit in batches

    def bulk_add_files(self, records: list[FileMetadata]) -> None:
        """Bulk-insert file records. Use after building a batch."""
        self._session.add_all(records)
        self._session.commit()

    def update_file_hash(
        self,
        file_id: int,
        md5: Optional[str] = None,
        sha256: Optional[str] = None,
        embedding: Optional[bytes] = None,
    ) -> None:
        """Patch hash/embedding fields on an existing FileMetadata row."""
        fm = self._session.get(FileMetadata, file_id)
        if not fm:
            return
        if md5:
            fm.md5_hash = md5
        if sha256:
            fm.sha256_hash = sha256
        if embedding:
            fm.embedding_vector = embedding
        self._session.commit()

    # ------------------------------------------------------------------
    # DuplicateGroup CRUD
    # ------------------------------------------------------------------

    def create_group(
        self,
        session_id: int,
        group_key: str,
        match_type: str,
        file_paths: list[str],
        space_recoverable_bytes: int = 0,
    ) -> DuplicateGroup:
        """Create a duplicate file group record."""
        grp = DuplicateGroup(
            session_id=session_id,
            group_key=group_key,
            match_type=match_type,
            group_size=len(file_paths),
            file_paths_json=json.dumps(file_paths),
            space_recoverable_bytes=space_recoverable_bytes,
        )
        self._session.add(grp)
        return grp

    def update_group_agent_decision(
        self,
        group_id: int,
        recommended_keep: str,
        confidence: float,
        reasoning: list[dict],
    ) -> None:
        """Persist agent recommendation on a group."""
        grp = self._session.get(DuplicateGroup, group_id)
        if grp:
            grp.agent_recommended_keep = recommended_keep
            grp.agent_confidence = confidence
            grp.agent_reasoning_json = json.dumps(reasoning)
            self._session.commit()

    def get_groups_for_session(self, session_id: int) -> list[DuplicateGroup]:
        return (
            self._session.execute(
                select(DuplicateGroup)
                .where(DuplicateGroup.session_id == session_id)
                .order_by(DuplicateGroup.space_recoverable_bytes.desc())
            )
            .scalars()
            .all()
        )

    # ------------------------------------------------------------------
    # FileAction (Audit Log)
    # ------------------------------------------------------------------

    def log_action(
        self,
        full_path: str,
        action: str,
        freed_bytes: int = 0,
        file_id: Optional[int] = None,
        agent_recommended: bool = False,
        method: str = "user",
    ) -> FileAction:
        """
        Record a file operation. Immutable once written.
        action: 'deleted' | 'kept' | 'quarantined' | 'skipped'
        """
        fa = FileAction(
            file_id=file_id,
            full_path=full_path,
            action=action,
            freed_bytes=freed_bytes,
            agent_recommended=agent_recommended,
            method=method,
            acted_at=datetime.now(timezone.utc).timestamp(),
        )
        self._session.add(fa)
        self._session.commit()
        return fa

    # ------------------------------------------------------------------
    # Aggregated Statistics
    # ------------------------------------------------------------------

    def get_lifetime_stats(self) -> dict:
        """
        Replaces the legacy lifetime_stats.json.
        Returns aggregated stats across all completed sessions.
        """
        result = self._session.execute(
            select(
                func.count(ScanSession.id).label("total_runs"),
                func.coalesce(func.sum(ScanSession.files_scanned), 0).label("total_files"),
                func.coalesce(func.sum(ScanSession.duplicate_groups), 0).label("total_groups"),
                func.coalesce(func.sum(ScanSession.duplicate_files), 0).label("total_dupes"),
            ).where(ScanSession.status == "completed")
        ).one()

        action_result = self._session.execute(
            select(
                func.count(FileAction.id).label("total_actions"),
                func.coalesce(func.sum(FileAction.freed_bytes), 0).label("space_freed"),
                func.count(FileAction.id).filter(FileAction.action == "deleted").label("deleted_count"),
            )
        ).one()

        return {
            "total_runs": result.total_runs,
            "total_files_scanned": result.total_files,
            "total_duplicate_groups": result.total_groups,
            "total_duplicate_files": result.total_dupes,
            "total_delete_operations": action_result.total_actions,
            "total_space_freed_bytes": action_result.space_freed,
            "total_files_deleted": action_result.deleted_count,
        }

    def get_space_saved_in_range(self, start: datetime, end: datetime) -> int:
        """Return bytes freed by deletions within the given UTC time range."""
        result = self._session.execute(
            select(func.coalesce(func.sum(FileAction.freed_bytes), 0)).where(
                FileAction.acted_at >= start.timestamp(),
                FileAction.acted_at <= end.timestamp(),
                FileAction.action == "deleted",
            )
        ).scalar()
        return int(result or 0)
