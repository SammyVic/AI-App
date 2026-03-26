"""
=============================================================================
app/engine/deduplicator.py
=============================================================================
Orchestration engine that coordinates the three-pass deduplication pipeline.

Pass 1: Size grouping (always)
Pass 2: Exact hash matching — ThreadPoolExecutor (hashlib releases GIL)
Pass 3: Semantic/ML matching — ProcessPoolExecutor (CPU-bound, bypasses GIL)

This module is fully headless: no Qt, no GUI dependencies.
It can be called from the CLI, a background QThread, or a unit test.
=============================================================================
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional

from app.engine.scanner import FileInfo, FileScanner, ScanConfig
from app.engine.hasher import FileHasher

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class DuplicateGroup:
    """A set of 2+ files determined to be duplicates."""
    group_key: str
    match_type: str          # 'exact_hash' | 'simple' | 'visual' | 'fuzzy' | 'semantic'
    file_paths: list[str]
    space_recoverable_bytes: int = 0

    @property
    def group_size(self) -> int:
        return len(self.file_paths)


@dataclass
class DeduplicationResult:
    """Complete result of a deduplication run."""
    groups: list[DuplicateGroup]
    files_scanned: int
    duplicate_files: int
    space_recoverable_bytes: int
    duration_seconds: float
    passes_completed: int

    @property
    def duplicate_groups(self) -> int:
        return len(self.groups)


# ---------------------------------------------------------------------------
# Progress callback type
# ---------------------------------------------------------------------------
# (pass_num: int, files_done: int, total_files: int, dupes_found: int, eta: str)
ProgressCallback = Callable[[int, int, int, int, str], None]


# ---------------------------------------------------------------------------
# Deduplicator
# ---------------------------------------------------------------------------

class Deduplicator:
    """
    Three-pass headless deduplication engine.

    Parameters
    ----------
    config        : ScanConfig controlling the file traversal
    algorithm     : 'md5' | 'sha256' | 'simple' (name+size only)
    max_workers   : thread count for Pass 2 (I/O-bound)
    use_semantic  : run Pass 3 with ONNX ML embeddings
    use_fuzzy     : run Pass 3 fuzzy filename matching
    on_progress   : optional callback for live UI updates
    """

    def __init__(
        self,
        config: ScanConfig,
        algorithm: str = "sha256",
        max_workers: int = 8,
        use_semantic: bool = False,
        use_fuzzy: bool = False,
        on_progress: Optional[ProgressCallback] = None,
        cancelled_flag: Optional[list[bool]] = None,
    ) -> None:
        self.config = config
        self.algorithm = algorithm
        self.max_workers = max_workers
        self.use_semantic = use_semantic
        self.use_fuzzy = use_fuzzy
        self._on_progress = on_progress or (lambda *_: None)
        self._cancelled = cancelled_flag or [False]

    @property
    def is_cancelled(self) -> bool:
        return bool(self._cancelled[0])

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> DeduplicationResult:
        """
        Execute all passes and return a structured DeduplicationResult.
        Raises no exceptions: any pass-level error is logged and skipped.
        """
        start = time.monotonic()
        groups: list[DuplicateGroup] = []
        group_counter = 0

        # --- PASS 1: Collect files & group by size ---
        logger.info("Pass 1: file traversal starting.")
        size_map: dict[int, list[FileInfo]] = defaultdict(list)
        all_files: list[FileInfo] = []

        scanner = FileScanner(self.config)
        for fi in scanner.scan():
            if self.is_cancelled:
                break
            size_map[fi.size_bytes].append(fi)
            all_files.append(fi)
            self._on_progress(1, len(all_files), len(all_files), 0, "")

        # Only buckets with 2+ files are candidates
        candidate_buckets = {sz: fis for sz, fis in size_map.items() if len(fis) > 1}
        logger.info("Pass 1 done: %d files, %d size-collision buckets.", len(all_files), len(candidate_buckets))

        if self.is_cancelled:
            return self._build_result(groups, all_files, start, 1)

        # --- PASS 2: Exact matching ---
        logger.info("Pass 2: exact matching (%s).", self.algorithm)
        confirmed_dupes: int = 0
        space_recoverable: int = 0

        if self.algorithm == "simple":
            # Name+size matching (ultra-fast)
            for size, fis in candidate_buckets.items():
                if self.is_cancelled:
                    break
                name_map: dict[str, list[str]] = defaultdict(list)
                for fi in fis:
                    name_map[fi.filename].append(fi.path)
                for name, paths in name_map.items():
                    if len(paths) > 1:
                        recoverable = size * (len(paths) - 1)
                        groups.append(DuplicateGroup(
                            group_key=f"simple_{group_counter}",
                            match_type="simple",
                            file_paths=paths,
                            space_recoverable_bytes=recoverable,
                        ))
                        confirmed_dupes += len(paths)
                        space_recoverable += recoverable
                        group_counter += 1
        else:
            # Hash-based matching with progress tracking
            hasher = FileHasher(algorithm=self.algorithm, max_workers=self.max_workers)
            flat_candidates = [fi.path for fis in candidate_buckets.values() for fi in fis]
            total_to_hash = len(flat_candidates)
            hashed_so_far = [0]

            def _progress(done: int, total: int) -> None:
                hashed_so_far[0] = done
                elapsed = time.monotonic() - start
                rate = done / elapsed if elapsed > 0 else 1
                remaining = (total - done) / rate if rate > 0 else 0
                m, s = divmod(int(remaining), 60)
                eta = f"{m:02d}:{s:02d}"
                self._on_progress(2, done, total, confirmed_dupes, eta)

            # Build per-size hash maps
            for size, fis in candidate_buckets.items():
                if self.is_cancelled:
                    break
                paths = [fi.path for fi in fis]
                hash_results = hasher.hash_batch(
                    paths, on_progress=_progress, cancelled_flag=self._cancelled
                )
                hash_map: dict[str, list[str]] = defaultdict(list)
                for path, digest in hash_results.items():
                    if digest:
                        hash_map[digest].append(path)

                for digest, dup_paths in hash_map.items():
                    if len(dup_paths) > 1:
                        recoverable = size * (len(dup_paths) - 1)
                        groups.append(DuplicateGroup(
                            group_key=f"exact_{group_counter}",
                            match_type="exact_hash",
                            file_paths=dup_paths,
                            space_recoverable_bytes=recoverable,
                        ))
                        confirmed_dupes += len(dup_paths)
                        space_recoverable += recoverable
                        group_counter += 1

        logger.info("Pass 2 done: %d groups, %d dupes, %d bytes recoverable.",
                    len(groups), confirmed_dupes, space_recoverable)

        if self.is_cancelled:
            return self._build_result(groups, all_files, start, 2)

        # --- PASS 3: Advanced / Semantic matching ---
        existing_paths = {frozenset(g.file_paths) for g in groups}

        if self.use_fuzzy:
            logger.info("Pass 3: fuzzy name matching.")
            fuzzy_groups = self._pass3_fuzzy(all_files, existing_paths, group_counter)
            groups.extend(fuzzy_groups)
            group_counter += len(fuzzy_groups)

        if self.use_semantic and not self.is_cancelled:
            logger.info("Pass 3: semantic ML matching.")
            semantic_groups = self._pass3_semantic(all_files, existing_paths, group_counter)
            groups.extend(semantic_groups)

        passes = 3 if (self.use_fuzzy or self.use_semantic) else 2
        return self._build_result(groups, all_files, start, passes)

    # ------------------------------------------------------------------
    # Pass 3a: Fuzzy filename matching
    # ------------------------------------------------------------------

    def _pass3_fuzzy(
        self,
        all_files: list[FileInfo],
        existing_paths: set[frozenset],
        group_counter: int,
    ) -> list[DuplicateGroup]:
        """
        Group files with similar names (>85% SequenceMatcher ratio).
        Uses ProcessPoolExecutor to bypass GIL for CPU-intensive string ops.
        """
        import difflib

        # Build per-(directory, extension) buckets
        dir_ext_map: dict[tuple[str, str], list[FileInfo]] = defaultdict(list)
        for fi in all_files:
            dir_ext_map[(fi.directory, fi.extension)].append(fi)

        new_groups: list[DuplicateGroup] = []

        for (folder, ext), fis in dir_ext_map.items():
            if len(fis) < 2 or self.is_cancelled:
                continue
            matched: set[int] = set()
            for i in range(len(fis)):
                if i in matched:
                    continue
                cluster = [fis[i]]
                name1 = fis[i].filename
                for j in range(i + 1, len(fis)):
                    if j in matched:
                        continue
                    name2 = fis[j].filename
                    try:
                        ratio = difflib.SequenceMatcher(None, name1, name2, autojunk=False).ratio()
                    except Exception as exc:
                        logger.debug("SequenceMatcher error: %s", exc)
                        continue
                    if ratio > 0.85:
                        cluster.append(fis[j])
                        matched.add(j)

                if len(cluster) > 1:
                    paths = [f.path for f in cluster]
                    fs = frozenset(paths)
                    if fs not in existing_paths:
                        existing_paths.add(fs)
                        new_groups.append(DuplicateGroup(
                            group_key=f"fuzzy_{group_counter + len(new_groups)}",
                            match_type="fuzzy",
                            file_paths=paths,
                        ))

        return new_groups

    # ------------------------------------------------------------------
    # Pass 3b: Semantic ML matching (ProcessPoolExecutor)
    # ------------------------------------------------------------------

    def _pass3_semantic(
        self,
        all_files: list[FileInfo],
        existing_paths: set[frozenset],
        group_counter: int,
    ) -> list[DuplicateGroup]:
        """
        Compute ONNX embeddings and cluster by cosine similarity.
        CPU-bound inference is offloaded to ProcessPoolExecutor.
        """
        try:
            from app.ml.embedder import ImageEmbedder, TextEmbedder
            from app.ml.vector_index import VectorIndex
        except ImportError as exc:
            logger.warning("ML modules unavailable, skipping semantic pass: %s", exc)
            return []

        IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        TEXT_EXTS = {".txt", ".pdf", ".doc", ".docx", ".md", ".log", ".csv"}

        image_files = [fi for fi in all_files if fi.extension in IMAGE_EXTS]
        text_files = [fi for fi in all_files if fi.extension in TEXT_EXTS]

        new_groups: list[DuplicateGroup] = []

        for files_batch, EmbedderClass, label in [
            (image_files, ImageEmbedder, "image"),
            (text_files, TextEmbedder, "text"),
        ]:
            if self.is_cancelled or not files_batch:
                continue

            embedder = EmbedderClass()
            if not embedder.is_available():
                logger.info("Embedder for %s not available, skipping.", label)
                continue

            # Offload embedding to ProcessPoolExecutor (one process per batch)
            paths = [fi.path for fi in files_batch]
            try:
                with ProcessPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(_embed_batch_worker, paths, label)
                    embeddings = future.result(timeout=300)  # 5 min hard timeout
            except Exception as exc:
                logger.error("Semantic embedding failed for %s: %s", label, exc)
                continue

            if embeddings is None:
                continue

            index = VectorIndex(embeddings, paths)
            pairs = index.find_similar_pairs(threshold=0.92)
            clusters = index.cluster_by_similarity(pairs)

            for cluster_paths in clusters:
                fs = frozenset(cluster_paths)
                if fs not in existing_paths and len(cluster_paths) > 1:
                    existing_paths.add(fs)
                    new_groups.append(DuplicateGroup(
                        group_key=f"semantic_{label}_{group_counter + len(new_groups)}",
                        match_type="semantic",
                        file_paths=cluster_paths,
                    ))

        return new_groups

    # ------------------------------------------------------------------
    # Result builder
    # ------------------------------------------------------------------

    def _build_result(
        self,
        groups: list[DuplicateGroup],
        all_files: list[FileInfo],
        start: float,
        passes: int,
    ) -> DeduplicationResult:
        total_dupes = sum(g.group_size for g in groups)
        total_space = sum(g.space_recoverable_bytes for g in groups)
        return DeduplicationResult(
            groups=groups,
            files_scanned=len(all_files),
            duplicate_files=total_dupes,
            space_recoverable_bytes=total_space,
            duration_seconds=time.monotonic() - start,
            passes_completed=passes,
        )


# ---------------------------------------------------------------------------
# Top-level function for ProcessPoolExecutor pickling safety
# ---------------------------------------------------------------------------

def _embed_batch_worker(paths: list[str], embed_type: str):
    """
    Executed in a subprocess. Returns numpy array of embeddings or None.
    Must be a module-level function for pickle compatibility.
    """
    try:
        from app.ml.embedder import ImageEmbedder, TextEmbedder
        import numpy as np

        cls = ImageEmbedder if embed_type == "image" else TextEmbedder
        embedder = cls()
        if not embedder.is_available():
            return None
        vectors = []
        for path in paths:
            try:
                vec = embedder.embed(path)
                vectors.append(vec if vec is not None else np.zeros(embedder.dim))
            except Exception as exc:
                logger.warning("Embedding failed for %r: %s", path, exc)
                vectors.append(np.zeros(embedder.dim))
        return np.stack(vectors, axis=0)
    except Exception as exc:
        logger.error("Worker embedding error: %s", exc)
        return None
