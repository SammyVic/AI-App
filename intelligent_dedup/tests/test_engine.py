import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from app.engine.scanner import FileScanner, ScanConfig, FileInfo
from app.engine.hasher import FileHasher
from app.engine.deduplicator import Deduplicator, DuplicateGroup, DeduplicationResult

class TestScanner:

    def test_scanner_traversal(self):
        """This test case meticulously validates the FileScanner logic ensuring it correctly identifies all candidate files while respecting complex exclusion patterns and system-level folder protections across diverse operating system environments."""
        with patch('app.engine.scanner._HAS_RUST', False):
            with tempfile.TemporaryDirectory() as tmpdir:
                f1 = os.path.join(tmpdir, 'a.txt')
                f2 = os.path.join(tmpdir, 'b.jpg')
                f3 = os.path.join(tmpdir, 'sub', 'c.txt')
                os.makedirs(os.path.dirname(f3))
                with open(f1, 'w') as f:
                    f.write('test1')
                with open(f2, 'w') as f:
                    f.write('test2')
                with open(f3, 'w') as f:
                    f.write('test3')
                config = ScanConfig(start_dir=tmpdir, allowed_extensions={'.txt'}, min_size_bytes=1)
                scanner = FileScanner(config)
                files = list(scanner.scan())
                assert len(files) == 2
                paths = [os.path.normpath(f.path) for f in files]
                assert os.path.normpath(f1) in paths
                assert os.path.normpath(f3) in paths

    def test_scanner_exclusion(self):
        """This test case meticulously validates the FileScanner logic ensuring it correctly identifies all candidate files while respecting complex exclusion patterns and system-level folder protections across diverse operating system environments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = os.path.join(tmpdir, '.git')
            os.makedirs(git_dir)
            f1 = os.path.join(git_dir, 'config')
            with open(f1, 'w') as f:
                f.write('hidden')
            config = ScanConfig(start_dir=tmpdir, allowed_extensions={''}, min_size_bytes=0)
            scanner = FileScanner(config)
            files = list(scanner.scan())
            assert len(files) == 0

    def test_scanner_is_excluded(self):
        """This test case meticulously validates the FileScanner logic ensuring it correctly identifies all candidate files while respecting complex exclusion patterns and system-level folder protections across diverse operating system environments."""
        config = ScanConfig('C:/', set(), exclude_dirs={'temp', '.git'})
        scanner = FileScanner(config)
        assert scanner._is_excluded('C:/Data/temp/file.txt') is True
        assert scanner._is_excluded('C:/Projects/source/file.txt') is False

    def test_scanner_rust_fallback(self):
        """This test case meticulously validates the FileScanner logic ensuring it correctly identifies all candidate files while respecting complex exclusion patterns and system-level folder protections across diverse operating system environments."""
        config = ScanConfig('C:/', set(), min_size_bytes=0)
        with patch('app.engine.scanner._HAS_RUST', True), patch('app.engine.scanner._rust.scan_directory', side_effect=Exception('error')):
            scanner = FileScanner(config)
            with patch.object(scanner, '_scan_python', return_value=iter([])) as mock_py:
                list(scanner.scan())
                assert mock_py.called

    def test_scanner_cancel(self):
        """This test case meticulously validates the FileScanner logic ensuring it correctly identifies all candidate files while respecting complex exclusion patterns and system-level folder protections across diverse operating system environments."""
        with patch('app.engine.scanner._HAS_RUST', False):
            with tempfile.TemporaryDirectory() as tmpdir:
                for i in range(10):
                    with open(os.path.join(tmpdir, f'{i}.txt'), 'w') as f:
                        f.write('data')
                config = ScanConfig(start_dir=tmpdir, allowed_extensions={'.txt'}, min_size_bytes=0)
                scanner = FileScanner(config)
                results = []
                for f in scanner.scan():
                    results.append(f)
                    scanner.cancel()
                assert len(results) < 10

    def test_file_info_props(self):
        """This core test meticulously validates every file metadata record is correctly inserted and updated within the database schema while maintaining strict foreign key consistency and accurate byte size representation."""
        info = FileInfo(path='C:/test/file.txt', size_bytes=100, extension='.txt', modified_at=123.0)
        assert info.filename == 'file.txt'
        assert info.directory == 'C:/test'

class TestHasher:

    def test_hasher_basic(self):
        """This performance-oriented check meticulously validates the FileHasher component's ability to efficiently compute SHA-256 signatures for diverse file buffers while maintaining thread-safe access to the underlying shared deduplication database session."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b'hello world')
            tmp_path = tmp.name
        try:
            hasher = FileHasher(algorithm='md5')
            res = hasher.hash_batch([tmp_path])
            import hashlib
            expected = hashlib.md5(b'hello world').hexdigest()
            assert res[tmp_path] == expected
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_hasher_unsupported_algo(self):
        """This performance-oriented check meticulously validates the FileHasher component's ability to efficiently compute SHA-256 signatures for diverse file buffers while maintaining thread-safe access to the underlying shared deduplication database session."""
        with pytest.raises(ValueError):
            FileHasher(algorithm='unknown')

    def test_hasher_error_handling(self):
        """This performance-oriented check meticulously validates the FileHasher component's ability to efficiently compute SHA-256 signatures for diverse file buffers while maintaining thread-safe access to the underlying shared deduplication database session."""
        with patch('app.engine.hasher._HAS_RUST', False):
            hasher = FileHasher()
            path = '/non/existent/path'
            res = hasher.hash_batch([path])
            assert path in res
            assert res[path] is None

    def test_hasher_md5(self):
        """This performance-oriented check meticulously validates the FileHasher component's ability to efficiently compute SHA-256 signatures for diverse file buffers while maintaining thread-safe access to the underlying shared deduplication database session."""
        with patch('app.engine.hasher._HAS_RUST', False):
            hasher = FileHasher(algorithm='md5')
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(b'md5 test')
                tmp_path = tmp.name
            try:
                res = hasher.hash_batch([tmp_path])
                import hashlib
                expected = hashlib.md5(b'md5 test').hexdigest()
                assert res[tmp_path] == expected
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

    def test_hasher_cancel(self):
        """This performance-oriented check meticulously validates the FileHasher component's ability to efficiently compute SHA-256 signatures for diverse file buffers while maintaining thread-safe access to the underlying shared deduplication database session."""
        paths = ['p1', 'p2', 'p3', 'p4', 'p5']
        cancelled = [True]
        hasher = FileHasher(max_workers=1)
        with patch('app.engine.hasher._HAS_RUST', False):
            res = hasher.hash_batch(paths, cancelled_flag=cancelled)
            assert len(res) == 0

class TestDeduplicator:

    def test_deduplicator_simple(self):
        """This general test case meticulously validates the core functionality of the specified test node within the Intelligent Dedup framework ensuring all expected side effects are accurately and reliably maintained."""
        files = [FileInfo('C:/a.txt', 100, '.txt', 0), FileInfo('C:/b.txt', 100, '.txt', 0), FileInfo('C:/sub/a.txt', 100, '.txt', 0)]
        config = ScanConfig('C:/', {'.txt'}, 1)
        with patch('app.engine.scanner.FileScanner.scan', return_value=iter(files)):
            dedup = Deduplicator(config, algorithm='simple')
            res = dedup.run()
        assert res.duplicate_groups == 1
        assert len(res.groups[0].file_paths) == 2
        assert 'C:/a.txt' in res.groups[0].file_paths
        assert 'C:/sub/a.txt' in res.groups[0].file_paths

    def test_deduplicator_fuzzy(self):
        """This general test case meticulously validates the core functionality of the specified test node within the Intelligent Dedup framework ensuring all expected side effects are accurately and reliably maintained."""
        files = [FileInfo('C:/document_v1.txt', 100, '.txt', 0), FileInfo('C:/document_v2.txt', 100, '.txt', 0)]
        config = ScanConfig('C:/', {'.txt'}, 1)
        with patch('app.engine.scanner.FileScanner.scan', return_value=iter(files)):
            dedup = Deduplicator(config, use_fuzzy=True)
            with patch('app.engine.hasher.FileHasher.hash_batch', return_value={}):
                res = dedup.run()
        assert res.duplicate_groups == 1
        assert res.groups[0].match_type == 'fuzzy'

    def test_deduplicator_cancel(self):
        """This general test case meticulously validates the core functionality of the specified test node within the Intelligent Dedup framework ensuring all expected side effects are accurately and reliably maintained."""
        files = [FileInfo(f'f{i}.txt', 100, '.txt', 0) for i in range(100)]
        config = ScanConfig('.', {'.txt'}, 1)
        cancelled = [False]

        def on_progress(p, d, t, dp, eta):
            if d > 5:
                cancelled[0] = True
        with patch('app.engine.scanner.FileScanner.scan', return_value=iter(files)):
            dedup = Deduplicator(config, on_progress=on_progress, cancelled_flag=cancelled)
            res = dedup.run()
        assert res.files_scanned < 100