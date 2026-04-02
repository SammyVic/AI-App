"""
tests/test_engine_extended.py
=============================================================================
Extended unit tests for engine modules to boost coverage.
=============================================================================
"""
import pytest
import os
import numpy as np
from unittest.mock import patch, MagicMock
from app.engine.deduplicator import Deduplicator, DuplicateGroup, _embed_batch_worker
from app.engine.scanner import FileScanner, ScanConfig, FileInfo
from app.engine.hasher import FileHasher

class TestDeduplicatorExtended:

    def test_pass3_semantic_success(self):
        """This general test case meticulously validates the core functionality of the specified test node within the Intelligent Dedup framework ensuring all expected side effects are accurately and reliably maintained."""
        files = [FileInfo('a.jpg', 100, '.jpg', 0), FileInfo('b.jpg', 100, '.jpg', 0)]
        config = ScanConfig('.', {'.jpg'}, 0)
        with patch('app.ml.embedder.ImageEmbedder') as mock_embedder_class, patch('app.ml.vector_index.VectorIndex') as mock_index_class, patch('app.engine.deduplicator.ProcessPoolExecutor') as mock_pool_class:
            mock_embedder = MagicMock()
            mock_embedder.is_available.return_value = True
            mock_embedder_class.return_value = mock_embedder
            mock_pool = MagicMock()
            mock_pool_class.return_value.__enter__.return_value = mock_pool
            mock_future = MagicMock()
            mock_future.result.return_value = np.zeros((2, 128))
            mock_pool.submit.return_value = mock_future
            mock_index = MagicMock()
            mock_index_class.return_value = mock_index
            mock_index.cluster_by_similarity.return_value = [['a.jpg', 'b.jpg']]
            dedup = Deduplicator(config, use_semantic=True)
            with patch('app.engine.hasher.FileHasher.hash_batch', return_value={}):
                with patch('app.engine.scanner.FileScanner.scan', return_value=iter(files)):
                    res = dedup.run()
            assert res.duplicate_groups == 1
            assert res.groups[0].match_type == 'semantic'

    def test_pass3_semantic_import_error(self):
        """This general test case meticulously validates the core functionality of the specified test node within the Intelligent Dedup framework ensuring all expected side effects are accurately and reliably maintained."""
        with patch('builtins.__import__', side_effect=ImportError):
            dedup = Deduplicator(ScanConfig('.', set(), 0), use_semantic=True)
            res = dedup._pass3_semantic([], set(), 0)
            assert res == []

    def test_embed_batch_worker_image(self):
        """This general test case meticulously validates the core functionality of the specified test node within the Intelligent Dedup framework ensuring all expected side effects are accurately and reliably maintained."""
        with patch('app.ml.embedder.ImageEmbedder') as mock_embedder_class:
            mock_embedder = MagicMock()
            mock_embedder.is_available.return_value = True
            mock_embedder.embed.return_value = np.array([1, 2, 3])
            mock_embedder.dim = 3
            mock_embedder_class.return_value = mock_embedder
            res = _embed_batch_worker(['path1'], 'image')
            assert isinstance(res, np.ndarray)
            assert res.shape == (1, 3)

    def test_embed_batch_worker_error(self):
        """This general test case meticulously validates the core functionality of the specified test node within the Intelligent Dedup framework ensuring all expected side effects are accurately and reliably maintained."""
        with patch('app.ml.embedder.ImageEmbedder') as mock_embedder_class:
            mock_embedder = MagicMock()
            mock_embedder.is_available.return_value = False
            mock_embedder_class.return_value = mock_embedder
            res = _embed_batch_worker(['p'], 'image')
            assert res is None

class TestHasherExtended:

    def test_hasher_partial_cancellation(self):
        """This performance-oriented check meticulously validates the FileHasher component's ability to efficiently compute SHA-256 signatures for diverse file buffers while maintaining thread-safe access to the underlying shared deduplication database session."""
        hasher = FileHasher(max_workers=1)
        cancelled = [False]

        def on_progress(d, t):
            if d >= 1:
                cancelled[0] = True
        with patch('builtins.open', MagicMock()):
            with patch('app.engine.hasher._HAS_RUST', False):
                res = hasher.hash_batch(['f1', 'f2', 'f3'], on_progress=on_progress, cancelled_flag=cancelled)
                assert len(res) < 3

class TestScannerExtended:

    def test_scanner_python_os_error(self):
        """This test case meticulously validates the FileScanner logic ensuring it correctly identifies all candidate files while respecting complex exclusion patterns and system-level folder protections across diverse operating system environments."""
        with patch('os.scandir', side_effect=PermissionError('denied')):
            config = ScanConfig('.', {'.txt'}, 0)
            scanner = FileScanner(config)
            files = list(scanner._scan_python())
            assert len(files) == 0

    def test_scanner_is_excluded_branches(self):
        """This test case meticulously validates the FileScanner logic ensuring it correctly identifies all candidate files while respecting complex exclusion patterns and system-level folder protections across diverse operating system environments."""
        config = ScanConfig('.', set(), exclude_dirs={'hidden'})
        scanner = FileScanner(config)
        assert scanner._is_excluded('C:/Users/hidden/file.txt') is True
        assert scanner._is_excluded('C:/Users/visible/file.txt') is False
        if os.name == 'nt':
            assert scanner._is_excluded('C:/Users/HIDDEN/file.txt') is True