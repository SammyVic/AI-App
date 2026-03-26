"""
=============================================================================
app/engine/hasher.py
=============================================================================
File hashing engine with ThreadPoolExecutor (hashlib releases the GIL).

Prefers the Rust PyO3 implementation (rayon parallel I/O + SHA-256).
Falls back to Python hashlib on import failure.

Supported algorithms: 'md5', 'sha256'
=============================================================================
"""

from __future__ import annotations

import hashlib
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try Rust extension
# ---------------------------------------------------------------------------
try:
    import rust_core as _rust  # type: ignore
    _HAS_RUST = True
except ImportError:
    _rust = None
    _HAS_RUST = False

# Default worker pool size
_DEFAULT_WORKERS = min(16, (os.cpu_count() or 4) * 2)

# ---------------------------------------------------------------------------
# Progress callback type
# ---------------------------------------------------------------------------
ProgressCallback = Callable[[int, int], None]  # (completed, total) -> None


# ---------------------------------------------------------------------------
# Main hasher class
# ---------------------------------------------------------------------------

class FileHasher:
    """
    Computes cryptographic hashes for a batch of files.

    Usage:
        hasher = FileHasher(algorithm='sha256', max_workers=8)
        results = hasher.hash_batch(paths, on_progress=lambda done, tot: ...)
        # results: dict[str, str | None]  (path -> hex_digest or None on error)
    """

    CHUNK_SIZE: int = 131_072  # 128 KB read window

    def __init__(
        self,
        algorithm: str = "sha256",
        max_workers: int = _DEFAULT_WORKERS,
    ) -> None:
        if algorithm not in ("md5", "sha256"):
            raise ValueError(f"Unsupported algorithm: {algorithm!r}. Use 'md5' or 'sha256'.")
        self.algorithm = algorithm
        self.max_workers = max_workers

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def hash_batch(
        self,
        paths: list[str],
        on_progress: Optional[ProgressCallback] = None,
        cancelled_flag: Optional[list[bool]] = None,
    ) -> dict[str, Optional[str]]:
        """
        Hash a list of file paths in parallel.

        Returns:
            dict mapping path -> hex_digest (None if the file was unreadable)
        """
        if not paths:
            return {}

        if _HAS_RUST:
            return self._hash_batch_rust(paths, on_progress, cancelled_flag)
        return self._hash_batch_python(paths, on_progress, cancelled_flag)

    # ------------------------------------------------------------------
    # Rust-backed batch hasher
    # ------------------------------------------------------------------

    def _hash_batch_rust(
        self,
        paths: list[str],
        on_progress: Optional[ProgressCallback],
        cancelled_flag: Optional[list[bool]],
    ) -> dict[str, Optional[str]]:
        try:
            results: dict[str, str] = _rust.hash_files_parallel(paths, self.algorithm)
            if on_progress:
                on_progress(len(paths), len(paths))
            return results
        except Exception as exc:
            logger.error("Rust hasher failed (%s), falling back to Python.", exc)
            return self._hash_batch_python(paths, on_progress, cancelled_flag)

    # ------------------------------------------------------------------
    # Python ThreadPoolExecutor fallback
    # ------------------------------------------------------------------

    def _hash_batch_python(
        self,
        paths: list[str],
        on_progress: Optional[ProgressCallback],
        cancelled_flag: Optional[list[bool]],
    ) -> dict[str, Optional[str]]:
        results: dict[str, Optional[str]] = {}
        total = len(paths)
        completed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_to_path = {
                pool.submit(self._hash_one, p): p for p in paths
            }
            for future in as_completed(future_to_path):
                if cancelled_flag and cancelled_flag[0]:
                    pool.shutdown(wait=False, cancel_futures=True)
                    break

                path = future_to_path[future]
                try:
                    results[path] = future.result()
                except Exception as exc:
                    logger.error("Hash future error for %r: %s", path, exc)
                    results[path] = None
                finally:
                    completed += 1
                    if on_progress:
                        on_progress(completed, total)

        return results

    # ------------------------------------------------------------------
    # Single file hash
    # ------------------------------------------------------------------

    def _hash_one(self, filepath: str) -> Optional[str]:
        """
        Compute hash for a single file.
        Explicitly catches PermissionError and OSError (never bare except).
        """
        h = hashlib.md5() if self.algorithm == "md5" else hashlib.sha256()
        try:
            with open(filepath, "rb") as fh:
                for chunk in iter(lambda: fh.read(self.CHUNK_SIZE), b""):
                    h.update(chunk)
            return h.hexdigest()
        except PermissionError as exc:
            logger.warning("Permission denied hashing %r: %s", filepath, exc)
            return None
        except OSError as exc:
            logger.warning("OS error hashing %r: %s", filepath, exc)
            return None
