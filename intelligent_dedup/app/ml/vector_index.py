"""
=============================================================================
app/ml/vector_index.py
=============================================================================
Pure NumPy cosine-similarity engine for clustering embedding vectors.

No scikit-learn dependency — uses BLAS-optimised np.dot for O(N²) pairwise
similarity. For N < 50,000 files this comfortably runs in under a second.
=============================================================================
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class VectorIndex:
    """
    Stores a matrix of L2-normalised embeddings and provides similarity search.

    Parameters
    ----------
    embeddings : np.ndarray of shape [N, D], dtype float32, L2-normalised.
    paths      : list[str] of length N — one path per row.
    """

    def __init__(self, embeddings: np.ndarray, paths: list[str]) -> None:
        if embeddings.ndim != 2:
            raise ValueError(f"Embeddings must be 2-D, got shape {embeddings.shape}")
        if len(paths) != embeddings.shape[0]:
            raise ValueError("len(paths) must equal embeddings.shape[0]")
        self._embeddings = embeddings.astype(np.float32)
        self._paths = paths

    @property
    def n(self) -> int:
        return len(self._paths)

    # ------------------------------------------------------------------
    # Pairwise cosine similarity
    # ------------------------------------------------------------------

    def cosine_similarity_matrix(self) -> np.ndarray:
        """
        Returns an [N, N] float32 matrix of pairwise cosine similarities.
        Assumes vectors are already L2-normalised → dot product = cosine sim.
        Uses np.dot which dispatches to optimised BLAS routines.
        """
        return np.dot(self._embeddings, self._embeddings.T)

    # ------------------------------------------------------------------
    # Pair finding
    # ------------------------------------------------------------------

    def find_similar_pairs(
        self, threshold: float = 0.92
    ) -> list[tuple[int, int, float]]:
        """
        Returns list of (i, j, similarity) for all pairs with sim >= threshold.
        Only upper-triangle pairs returned (i < j) to avoid duplicates.
        """
        sim_matrix = self.cosine_similarity_matrix()
        # Zero out diagonal and lower triangle
        mask = np.triu(np.ones((self.n, self.n), dtype=bool), k=1)
        sim_masked = np.where(mask, sim_matrix, 0.0)
        ii, jj = np.where(sim_masked >= threshold)
        pairs = [
            (int(i), int(j), float(sim_masked[i, j]))
            for i, j in zip(ii, jj)
        ]
        # Sort by similarity descending for deterministic cluster order
        pairs.sort(key=lambda x: -x[2])
        return pairs

    # ------------------------------------------------------------------
    # Greedy connected-component clustering
    # ------------------------------------------------------------------

    def cluster_by_similarity(
        self, pairs: Optional[list[tuple[int, int, float]]] = None
    ) -> list[list[str]]:
        """
        Groups indices into clusters using greedy union-find (disjoint set).
        A cluster is included only if it has 2+ members.

        Returns
        -------
        list of clusters, where each cluster is a list of file paths.
        """
        if pairs is None:
            pairs = self.find_similar_pairs()

        # Union-Find
        parent = list(range(self.n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]  # path compression
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry

        for i, j, _ in pairs:
            union(i, j)

        # Collect clusters
        from collections import defaultdict
        clusters: dict[int, list[str]] = defaultdict(list)
        for idx in range(self.n):
            root = find(idx)
            clusters[root].append(self._paths[idx])

        return [v for v in clusters.values() if len(v) > 1]

    # ------------------------------------------------------------------
    # Batch similarity for a query vector
    # ------------------------------------------------------------------

    def query(self, vector: np.ndarray, top_k: int = 10) -> list[tuple[str, float]]:
        """
        Find top_k most similar paths to a query embedding vector.

        Returns
        -------
        list of (path, similarity) sorted by similarity descending.
        """
        v = vector.astype(np.float32)
        norm = np.linalg.norm(v)
        if norm > 1e-9:
            v = v / norm
        sims = np.dot(self._embeddings, v)
        indices = np.argsort(-sims)[:top_k]
        return [(self._paths[i], float(sims[i])) for i in indices]
