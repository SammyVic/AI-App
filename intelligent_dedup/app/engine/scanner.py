"""
=============================================================================
app/engine/scanner.py
=============================================================================
Headless file traversal engine.

Attempts to use the Rust PyO3 extension (rust_core) for maximum throughput.
Falls back automatically to pure-Python os.walk on import failure.

All OSError / PermissionError exceptions are explicitly caught and logged
(never silenced) so users can diagnose access problems.
=============================================================================
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import Iterator, Set, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try to import the compiled Rust extension
# ---------------------------------------------------------------------------
try:
    import rust_core as _rust  # type: ignore
    _HAS_RUST = True
    logger.info("rust_core loaded — using native scanner.")
except ImportError:
    _rust = None
    _HAS_RUST = False
    logger.info("rust_core not available — using Python fallback scanner.")

# ---------------------------------------------------------------------------
# System paths that should never be scanned
# ---------------------------------------------------------------------------
SYSTEM_EXCLUSIONS: frozenset[str] = frozenset({
    "windows", "appdata", "program files", "program files (x86)",
    ".git", ".svn", ".hg", "node_modules", "system32",
    "$recycle.bin", "__pycache__", ".venv", "venv", ".tox",
})

# ---------------------------------------------------------------------------
# Data container for a single discovered file
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class FileInfo:
    """Immutable record for one discovered file."""
    path: str
    size_bytes: int
    extension: str          # lowercase, including dot: '.jpg'
    modified_at: float      # unix timestamp
    is_symlink: bool = False

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    @property
    def directory(self) -> str:
        return os.path.dirname(self.path)


# ---------------------------------------------------------------------------
# ScanConfig — parameters for a single scan
# ---------------------------------------------------------------------------

@dataclass
class ScanConfig:
    """All parameters that control a single file scan."""
    start_dir: str
    allowed_extensions: Set[str]        # e.g. {'.jpg', '.png'}
    min_size_bytes: int = 1024          # default 1 KB
    exclude_dirs: frozenset[str] = field(default_factory=lambda: SYSTEM_EXCLUSIONS)
    follow_symlinks: bool = False


# ---------------------------------------------------------------------------
# FileScanner
# ---------------------------------------------------------------------------

class FileScanner:
    """
    Recursively walks a directory and yields FileInfo objects.

    Usage (headless):
        config = ScanConfig(start_dir="/data", allowed_extensions={'.jpg'})
        for file_info in FileScanner(config):
            process(file_info)
    """

    def __init__(self, config: ScanConfig) -> None:
        self.config = config
        self._cancelled: bool = False

    def cancel(self) -> None:
        """Signal the scanner to stop after the current file."""
        self._cancelled = True

    def scan(self) -> Iterator[FileInfo]:
        """
        Main entry point. Prefers Rust backend, falls back to Python.
        Yields FileInfo for every qualifying file.
        """
        if _HAS_RUST:
            yield from self._scan_rust()
        else:
            yield from self._scan_python()

    # Alias so scanner is iterable directly
    def __iter__(self) -> Iterator[FileInfo]:
        return self.scan()

    # ------------------------------------------------------------------
    # Rust-backed scanner
    # ------------------------------------------------------------------

    def _scan_rust(self) -> Iterator[FileInfo]:
        """
        Delegates to rust_core.scan_directory().
        Rust returns a list of dicts:
          {path: str, size: int, ext: str, modified_secs: float}
        """
        try:
            results: list[dict] = _rust.scan_directory(
                self.config.start_dir,
                list(self.config.allowed_extensions),
                self.config.min_size_bytes,
            )
            for r in results:
                if self._cancelled:
                    return
                # Apply Python-side exclusion check (belt-and-suspenders)
                if self._is_excluded(r["path"]):
                    continue
                yield FileInfo(
                    path=os.path.normpath(r["path"]),
                    size_bytes=int(r["size"]),
                    extension=r["ext"].lower(),
                    modified_at=float(r["modified_secs"]),
                    is_symlink=bool(r.get("is_symlink", False)),
                )
        except Exception as exc:
            logger.error("Rust scanner failed (%s), falling back to Python.", exc)
            yield from self._scan_python()

    # ------------------------------------------------------------------
    # Pure-Python fallback scanner
    # ------------------------------------------------------------------

    def _scan_python(self) -> Iterator[FileInfo]:
        """
        Pure-Python os.walk based scanner.
        Explicitly catches OSError / PermissionError instead of bare except.
        """
        cfg = self.config
        for root, dirs, files in os.walk(cfg.start_dir, followlinks=cfg.follow_symlinks):
            if self._cancelled:
                return

            # Filter system dirs in-place (mutates dirs to prune walk)
            dirs[:] = [
                d for d in dirs
                if d.lower() not in cfg.exclude_dirs and not d.startswith(".")
            ]

            for filename in files:
                if self._cancelled:
                    return

                ext = os.path.splitext(filename)[1].lower()
                if ext not in cfg.allowed_extensions:
                    continue

                full_path = os.path.join(root, filename)

                try:
                    is_link = os.path.islink(full_path)
                    if is_link and not cfg.follow_symlinks:
                        continue

                    stat = os.stat(full_path)
                    size = stat.st_size
                    if size < cfg.min_size_bytes:
                        continue

                    yield FileInfo(
                        path=os.path.normpath(full_path),
                        size_bytes=size,
                        extension=ext,
                        modified_at=stat.st_mtime,
                        is_symlink=is_link,
                    )

                except PermissionError as exc:
                    logger.warning("Permission denied: %s — %s", full_path, exc)
                except OSError as exc:
                    logger.warning("OS error reading %s — %s", full_path, exc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_excluded(self, path: str) -> bool:
        """Check if any path component is in the exclusion list."""
        parts = path.replace("\\", "/").split("/")
        return any(p.lower() in self.config.exclude_dirs for p in parts)
