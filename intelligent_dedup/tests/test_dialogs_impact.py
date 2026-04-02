"""
tests/test_dialogs_impact.py
=============================================================================
High-impact integration tests for dialogs using pytest-qt and qtbot.
Actually instantiates the dialogs to exercise __init__ and UI setup code.
=============================================================================
"""
import pytest
from PyQt6.QtCore import Qt
from app.views.dialogs.stats_dialog import StatsDialog
from app.views.dialogs.load_session_dialog import LoadSessionDialog
from unittest.mock import MagicMock

def test_stats_dialog_full_init(qtbot):
    """Exercise StatsDialog.__init__ and table population."""
    stats = {
        "total_runs": 5,
        "total_files_scanned": 1000,
        "total_duplicate_groups": 50,
        "total_duplicate_files": 200,
        "total_files_deleted": 100,
        "total_delete_operations": 12,
        "total_space_freed_bytes": 10 * 1024**3, # 10 GB
        "last_run_date": "2026-01-01",
        "last_run_deleted": 5,
        "last_run_space": 10 * 1024**2 # 10 MB
    }
    dlg = StatsDialog(None, stats)
    qtbot.addWidget(dlg)
    
    assert dlg.windowTitle() == "📊 Lifetime Statistics"
    # 10 metrics expected
    assert dlg.table.rowCount() == 10
    assert dlg.table.item(0, 1).text() == "5" # total_runs
    assert dlg.table.item(6, 1).text() == "10.00 GB" # total_space_freed
    assert dlg.table.item(9, 1).text() == "10.00 MB" # last_run_space

def test_stats_dialog_empty_stats(qtbot):
    """Verify StatsDialog handles missing stats dict gracefully."""
    dlg = StatsDialog(None, None)
    qtbot.addWidget(dlg)
    assert dlg.table.rowCount() == 10
    assert dlg.table.item(0, 1).text() == "0"
    assert dlg.table.item(7, 1).text() == "Never"

def test_load_session_dialog_full_init(qtbot):
    """Exercise LoadSessionDialog.__init__ and _build_ui."""
    sess1 = MagicMock()
    sess1.id = 42
    sess1.started_at_human.return_value = "2026-03-28"
    sess1.folder_path = "C:/Test"
    sess1.files_scanned = 500
    sess1.duplicate_groups = 25
    
    dlg = LoadSessionDialog(None, [sess1])
    qtbot.addWidget(dlg)
    
    assert dlg.table.rowCount() == 1
    assert dlg.table.item(0, 0).text() == "42"
    assert dlg.table.item(0, 2).text() == "C:/Test"
    assert dlg.table.item(0, 0).data(Qt.ItemDataRole.UserRole) == 42

def test_load_session_dialog_selection(qtbot):
    """Exercise _on_accept when a row is selected or not."""
    sess1 = MagicMock()
    sess1.id = 101
    sess1.started_at_human.return_value = "date"
    sess1.folder_path = "p"
    sess1.files_scanned = 0
    sess1.duplicate_groups = 0
    
    dlg = LoadSessionDialog(None, [sess1])
    qtbot.addWidget(dlg)

    # Initially no selection
    dlg.table.setCurrentCell(-1, -1)
    
    # Mocking accept/reject to check logic
    dlg.accept = MagicMock()
    dlg.reject = MagicMock()
    
    # 1. Reject Case: Click "Load Session" without selecting row
    # (Actually currentRow returns -1 when nothing is selected)
    qtbot.mouseClick(dlg.btn_load, Qt.MouseButton.LeftButton)
    dlg.reject.assert_called_once()
    assert dlg.selected_session_id is None
    
    # 2. Accept Case: Select row 0 and click "Load Session"
    dlg.reject.reset_mock()
    dlg.table.setCurrentCell(0, 0)
    qtbot.mouseClick(dlg.btn_load, Qt.MouseButton.LeftButton)
    dlg.accept.assert_called_once()
    assert dlg.selected_session_id == 101

    # 3. Double-Click Case
    dlg.accept.reset_mock()
    # Trigger double click by direct signal since mouseClick on table item is flaky in headless
    dlg.table.itemDoubleClicked.emit(dlg.table.item(0,0))
    dlg.accept.assert_called_once()
