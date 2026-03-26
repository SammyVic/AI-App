"""
=============================================================================
app/models/database.py
=============================================================================
SQLAlchemy ORM schema for Intelligent Duplicate Finder.

Tables:
  - ScanSession     : one record per user-initiated scan
  - FileMetadata    : every file discovered during a session
  - DuplicateGroup  : a cluster of duplicate files within a session
  - FileAction      : audit log of every delete / keep / skip operation

Design decisions:
  - SQLite backend, WAL journal mode for concurrent reads during long scans
  - Foreign keys enforced via pragma
  - Embeddings stored as BLOB (serialized numpy float32 array)
  - All timestamps are UTC unix float for portable sorting
=============================================================================
"""

from __future__ import annotations

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    create_engine, event, text,
    Column, Integer, String, Float, Boolean, LargeBinary,
    ForeignKey, Index, UniqueConstraint,
)
from sqlalchemy.orm import (
    DeclarativeBase, relationship, sessionmaker, Session,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database location — respects XDG-style app config dir
# ---------------------------------------------------------------------------
_DEFAULT_DB_PATH = os.path.join(
    os.path.expanduser("~"), ".intelligent_dedup", "dedup.db"
)

# ---------------------------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ScanSession(Base):
    """
    One record per user-initiated scan run.
    Replaces the flat lifetime_stats.json and scan_history/*.json files.
    """
    __tablename__ = "scan_sessions"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    folder_path: str = Column(String(2048), nullable=False, index=True)
    started_at: float = Column(Float, nullable=False, default=lambda: datetime.now(timezone.utc).timestamp())
    completed_at: Optional[float] = Column(Float, nullable=True)
    duration_seconds: Optional[float] = Column(Float, nullable=True)

    files_scanned: int = Column(Integer, default=0)
    duplicate_groups: int = Column(Integer, default=0)
    duplicate_files: int = Column(Integer, default=0)
    space_recoverable_bytes: int = Column(Integer, default=0)

    comparison_method: str = Column(String(64), default="sha256")  # 'md5' | 'sha256' | 'simple'
    used_semantic: bool = Column(Boolean, default=False)
    used_fuzzy: bool = Column(Boolean, default=False)
    used_phash: bool = Column(Boolean, default=False)

    status: str = Column(String(32), default="running")  # 'running' | 'completed' | 'cancelled' | 'error'
    error_message: Optional[str] = Column(String(4096), nullable=True)

    # Relationships
    files: list["FileMetadata"] = relationship(
        "FileMetadata", back_populates="session", cascade="all, delete-orphan", lazy="dynamic"
    )
    groups: list["DuplicateGroup"] = relationship(
        "DuplicateGroup", back_populates="session", cascade="all, delete-orphan", lazy="dynamic"
    )

    def started_at_human(self) -> str:
        return datetime.fromtimestamp(self.started_at).strftime("%Y-%m-%d %H:%M:%S")

    def __repr__(self) -> str:
        return f"<ScanSession id={self.id} folder={self.folder_path!r} status={self.status!r}>"


class FileMetadata(Base):
    """
    Every file discovered during a scan session.
    Stores hashes lazily (populated when computed in Pass 2).
    Embedding vector is a serialized float32 numpy array (optional, Pass 3 only).
    """
    __tablename__ = "file_metadata"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    session_id: int = Column(Integer, ForeignKey("scan_sessions.id", ondelete="CASCADE"), nullable=False)

    full_path: str = Column(String(4096), nullable=False)
    filename: str = Column(String(512), nullable=False)
    extension: str = Column(String(32), nullable=False)
    size_bytes: int = Column(Integer, nullable=False)
    modified_at: float = Column(Float, nullable=False)  # unix timestamp

    md5_hash: Optional[str] = Column(String(32), nullable=True, index=True)
    sha256_hash: Optional[str] = Column(String(64), nullable=True, index=True)
    embedding_vector: Optional[bytes] = Column(LargeBinary, nullable=True)  # serialized np.ndarray

    is_symlink: bool = Column(Boolean, default=False)

    # Relationships
    session: "ScanSession" = relationship("ScanSession", back_populates="files")
    actions: list["FileAction"] = relationship(
        "FileAction", back_populates="file", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_file_session_path", "session_id", "full_path"),
    )

    def __repr__(self) -> str:
        return f"<FileMetadata id={self.id} path={self.full_path!r}>"


class DuplicateGroup(Base):
    """
    A cluster of 2+ files determined to be duplicates within a session.
    Stores serialized JSON list of full_paths as the group manifest.
    """
    __tablename__ = "duplicate_groups"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    session_id: int = Column(Integer, ForeignKey("scan_sessions.id", ondelete="CASCADE"), nullable=False)

    group_key: str = Column(String(256), nullable=False)   # e.g. "exact_0", "visual_12"
    match_type: str = Column(String(32), nullable=False)   # 'exact_hash' | 'visual' | 'fuzzy' | 'simple' | 'semantic'
    group_size: int = Column(Integer, nullable=False)       # number of files in group

    file_paths_json: str = Column(String, nullable=False)  # JSON array of absolute paths
    space_recoverable_bytes: int = Column(Integer, default=0)

    # Agent fields
    agent_recommended_keep: Optional[str] = Column(String(4096), nullable=True)
    agent_confidence: Optional[float] = Column(Float, nullable=True)
    agent_reasoning_json: Optional[str] = Column(String, nullable=True)  # JSON reasoning log

    # Relationships
    session: "ScanSession" = relationship("ScanSession", back_populates="groups")

    __table_args__ = (
        Index("ix_group_session_key", "session_id", "group_key"),
    )

    @property
    def file_paths(self) -> list[str]:
        return json.loads(self.file_paths_json) if self.file_paths_json else []

    @file_paths.setter
    def file_paths(self, paths: list[str]) -> None:
        self.file_paths_json = json.dumps(paths)

    def __repr__(self) -> str:
        return f"<DuplicateGroup id={self.id} key={self.group_key!r} type={self.match_type!r} size={self.group_size}>"


class FileAction(Base):
    """
    Immutable audit log: one row per file operation (delete, keep, skip).
    Enables full history reconstruction and space-saved analytics.
    """
    __tablename__ = "file_actions"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    file_id: int = Column(Integer, ForeignKey("file_metadata.id", ondelete="SET NULL"), nullable=True)

    full_path: str = Column(String(4096), nullable=False)   # denormalized for post-delete lookup
    action: str = Column(String(32), nullable=False)         # 'deleted' | 'kept' | 'quarantined' | 'skipped'
    acted_at: float = Column(Float, nullable=False, default=lambda: datetime.now(timezone.utc).timestamp())

    freed_bytes: int = Column(Integer, default=0)
    agent_recommended: bool = Column(Boolean, default=False)  # Was this the agent's recommendation?
    method: str = Column(String(32), default="user")  # 'user' | 'agent' | 'profile'

    # Relationship
    file: Optional["FileMetadata"] = relationship("FileMetadata", back_populates="actions")

    def __repr__(self) -> str:
        return f"<FileAction id={self.id} action={self.action!r} path={self.full_path!r}>"


# ---------------------------------------------------------------------------
# Engine & Session Factory
# ---------------------------------------------------------------------------

def _get_db_path(custom_path: Optional[str] = None) -> str:
    path = custom_path or os.environ.get("DEDUP_DB_PATH") or _DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def create_db_engine(db_path: Optional[str] = None):
    """
    Create an SQLAlchemy engine with WAL journal mode and FK enforcement.
    """
    db_url = f"sqlite:///{_get_db_path(db_path)}"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Enable WAL mode + foreign keys on every new connection
    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

    return engine


def init_db(db_path: Optional[str] = None):
    """
    Initialize the database: create all tables if they don't exist.
    Returns a configured SessionLocal factory.
    """
    engine = create_db_engine(db_path)
    Base.metadata.create_all(engine)
    logger.info("Database initialised at: %s", _get_db_path(db_path))
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
