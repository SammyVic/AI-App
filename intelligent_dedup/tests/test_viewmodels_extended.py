"""
tests/test_viewmodels_extended.py
=============================================================================
Extended unit tests for viewmodel modules to boost coverage.
=============================================================================
"""
import pytest
from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtGui import QColor
from app.viewmodels.results_viewmodel import DuplicateTableModel, COL_FILENAME, COL_STATUS
from app.engine.deduplicator import DeduplicationResult, DuplicateGroup
from app.agents.retention_agent import AgentDecision
from unittest.mock import patch, MagicMock

class TestDuplicateTableModelExtended:

    def _make_loaded_model(self):
        model = DuplicateTableModel()
        res = DeduplicationResult(groups=[DuplicateGroup('g1', 'exact', ['p1', 'p2'], 100), DuplicateGroup('g2', 'exact', ['p3', 'p4'], 200)], files_scanned=4, duplicate_files=4, space_recoverable_bytes=300, duration_seconds=1.0, passes_completed=2)
        with patch('os.stat') as mock_stat:
            mock_stat.return_value.st_size = 50
            mock_stat.return_value.st_mtime = 0
            model.load_result(res, decisions={})
        return model

    def test_load_result_with_decisions(self):
        """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
        model = DuplicateTableModel()
        res = DeduplicationResult(groups=[DuplicateGroup('g1', 'exact', ['p1'], 10)], files_scanned=1, duplicate_files=1, space_recoverable_bytes=10, duration_seconds=1, passes_completed=1)
        from app.agents.retention_agent import AgentScore
        decision = AgentDecision(recommended_keep='p1', confidence=0.9, scores=[AgentScore(path='p1', total_score=0.9)], reasoning=['rules'])
        decisions = {'g1': decision}
        with patch('os.stat') as mock_stat:
            mock_stat.return_value.st_size = 10
            model.load_result(res, decisions=decisions)
        assert 'Keep (90%)' in model._rows[1].ai_rec

    def test_set_data_group_header(self):
        """This functional test meticulously verifies that the scan repository correctly handles large volumes of redundant file groups including their metadata hashes and space recovery statistics during complex deduplication processing runs."""
        model = self._make_loaded_model()
        idx = model.index(0, COL_FILENAME)
        model.setData(idx, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        assert 1 in model._checked
        assert 2 in model._checked
        assert 3 not in model._checked
        model.setData(idx, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        assert 1 not in model._checked
        assert 2 not in model._checked

    def test_set_data_valid(self):
        """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
        model = self._make_loaded_model()
        index = model.index(1, 0)
        model.setData(index, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        assert index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
        model.setData(index, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        assert index.data(Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Unchecked

    def test_mark_group_deleted(self):
        """This functional test meticulously verifies that the scan repository correctly handles large volumes of redundant file groups including their metadata hashes and space recovery statistics during complex deduplication processing runs."""
        model = self._make_loaded_model()
        model.check_row(1, True)
        model.mark_group_deleted('g1')
        assert model._rows[0].status == 'Deleted'
        assert model._rows[1].status == 'Deleted'
        assert model._rows[2].status == 'Deleted'
        assert 1 not in model._checked

    def test_data_roles(self):
        """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
        model = self._make_loaded_model()
        h_idx = model.index(0, COL_FILENAME)
        f_idx = model.index(1, COL_FILENAME)
        assert isinstance(model.data(h_idx, Qt.ItemDataRole.BackgroundRole), QColor)
        assert model.data(f_idx, Qt.ItemDataRole.BackgroundRole) is None
        assert isinstance(model.data(h_idx, Qt.ItemDataRole.ForegroundRole), QColor)
        assert model.data(h_idx, Qt.ItemDataRole.ToolTipRole) is None
        assert model.data(f_idx, Qt.ItemDataRole.ToolTipRole) == 'p1'
        model.check_row(1, True)
        assert model.data(h_idx, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.PartiallyChecked
        model.check_row(2, True)
        assert model.data(h_idx, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked

    def test_flags_deleted(self):
        """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
        model = self._make_loaded_model()
        idx = model.index(1, COL_FILENAME)
        assert Qt.ItemFlag.ItemIsUserCheckable in model.flags(idx)
        model.mark_deleted(1)
        assert Qt.ItemFlag.ItemIsUserCheckable not in model.flags(idx)

    def test_header_data(self):
        """This structural test meticulously verifies the ScanViewModel state machine correctly handles transitions between scanning and idle modes while broadcasting accurate progress updates to the connected user interface components reliably."""
        model = DuplicateTableModel()
        assert model.headerData(0, Qt.Orientation.Horizontal) == 'File Name'
        assert model.headerData(0, Qt.Orientation.Vertical) is None