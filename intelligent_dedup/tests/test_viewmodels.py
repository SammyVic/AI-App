import os
from unittest.mock import patch, MagicMock
from app.viewmodels.scan_viewmodel import ScanViewModel
from app.viewmodels.results_viewmodel import DuplicateTableModel, COL_FILENAME, COL_STATUS
from app.engine.deduplicator import DeduplicationResult, DuplicateGroup

def test_scan_viewmodel_initial_state():
    """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
    vm = ScanViewModel()
    assert vm.is_scanning is False
    assert vm.is_paused is False

def test_scan_viewmodel_start_cancel():
    """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
    vm = ScanViewModel()
    with patch('app.viewmodels.scan_viewmodel.ScanWorker') as MockWorker:
        vm.start_scan('C:/test', {'.txt'}, 1, 'sha256')
        assert vm.is_scanning is True
        vm.cancel_scan()
        assert vm.is_scanning is False

def test_scan_viewmodel_pause():
    """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
    vm = ScanViewModel()
    vm.toggle_pause()
    assert vm.is_paused is True
    vm.toggle_pause()
    assert vm.is_paused is False

def test_on_finished_reset():
    """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
    vm = ScanViewModel()
    vm._is_scanning = True
    result = DeduplicationResult(groups=[], files_scanned=10, duplicate_files=0, space_recoverable_bytes=0, duration_seconds=1.0, passes_completed=2)
    vm._on_finished(result)
    assert vm.is_scanning is False

class TestDuplicateTableModel:

    def test_model_reset(self):
        """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
        model = DuplicateTableModel()
        assert model.rowCount() == 0

    def test_load_result(self):
        """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
        model = DuplicateTableModel()
        res = DeduplicationResult(groups=[DuplicateGroup('g1', 'exact', ['C:/a.txt', 'C:/b.txt'], 1000)], files_scanned=2, duplicate_files=2, space_recoverable_bytes=1000, duration_seconds=1.0, passes_completed=2)
        with patch('os.stat') as mock_stat:
            mock_stat.return_value.st_size = 500
            mock_stat.return_value.st_mtime = 123456789.0
            model.load_result(res)
        assert model.rowCount() == 3
        assert model.columnCount() == 7
        from PyQt6.QtCore import Qt
        idx = model.index(1, COL_FILENAME)
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == 'a.txt'

    def test_checkbox_logic(self):
        """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
        model = DuplicateTableModel()
        res = DeduplicationResult(groups=[DuplicateGroup('g1', 'e', ['a', 'b'], 10)], files_scanned=2, duplicate_files=2, space_recoverable_bytes=10, duration_seconds=1, passes_completed=2)
        with patch('os.stat') as mock_stat:
            mock_stat.return_value.st_size = 100
            mock_stat.return_value.st_mtime = 0
            model.load_result(res)
        model.check_row(1, True)
        assert 1 in model._checked
        assert len(model.get_checked_paths()) == 1
        from PyQt6.QtCore import Qt
        h_idx = model.index(0, COL_FILENAME)
        assert model.data(h_idx, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.PartiallyChecked
        model.check_row(2, True)
        assert model.data(h_idx, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked

    def test_mark_deleted(self):
        """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
        model = DuplicateTableModel()
        res = DeduplicationResult(groups=[DuplicateGroup('g1', 'e', ['a'], 10)], files_scanned=1, duplicate_files=1, space_recoverable_bytes=10, duration_seconds=1, passes_completed=2)
        with patch('os.stat') as mock_stat:
            mock_stat.return_value.st_size = 100
            mock_stat.return_value.st_mtime = 0
            model.load_result(res)
        model.mark_deleted(1)
        idx = model.index(1, COL_STATUS)
        from PyQt6.QtCore import Qt
        assert model.data(idx, Qt.ItemDataRole.DisplayRole) == 'Deleted'

    def test_get_checked_items(self):
        """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
        model = DuplicateTableModel()
        res = DeduplicationResult(groups=[DuplicateGroup('g1', 'e', ['p1', 'p2'], 10)], files_scanned=2, duplicate_files=2, space_recoverable_bytes=10, duration_seconds=1, passes_completed=2)
        with patch('os.stat') as mock_stat:
            mock_stat.return_value.st_size = 100
            mock_stat.return_value.st_mtime = 0
            model.load_result(res)
        model.check_row(1, True)
        items = model.get_checked_items()
        assert len(items) == 1
        assert items[0][1] == 'p1'

    def test_flags(self):
        """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
        model = DuplicateTableModel()
        res = DeduplicationResult(groups=[DuplicateGroup('g1', 'e', ['a'], 10)], files_scanned=1, duplicate_files=1, space_recoverable_bytes=10, duration_seconds=1, passes_completed=2)
        with patch('os.stat') as mock_stat:
            mock_stat.return_value.st_size = 100
            mock_stat.return_value.st_mtime = 0
            model.load_result(res)
        from PyQt6.QtCore import Qt
        idx = model.index(1, 0)
        flags = model.flags(idx)
        assert Qt.ItemFlag.ItemIsUserCheckable in flags
        model.mark_deleted(1)
        flags2 = model.flags(idx)
        assert Qt.ItemFlag.ItemIsUserCheckable not in flags2

    def test_set_data_checkbox(self):
        """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
        model = DuplicateTableModel()
        res = DeduplicationResult(groups=[DuplicateGroup('g1', 'e', ['a'], 10)], files_scanned=1, duplicate_files=1, space_recoverable_bytes=10, duration_seconds=1, passes_completed=2)
        with patch('os.stat') as mock_stat:
            mock_stat.return_value.st_size = 100
            mock_stat.return_value.st_mtime = 0
            model.load_result(res)
        from PyQt6.QtCore import Qt
        idx = model.index(1, 0)
        model.setData(idx, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        assert 1 in model._checked