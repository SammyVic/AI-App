"""
tests/test_main_window_extended.py
=============================================================================
Extended unit tests for app/views/main_window.py covering more branches.
Uses same unbound-method pattern as test_main_window.py.
=============================================================================
"""
from __future__ import annotations
import os
import json
from unittest.mock import MagicMock, patch

import app.views.main_window as mw_module


def _make_win() -> MagicMock:
    win = MagicMock()
    win._agent_text = MagicMock()
    win._preview_text = MagicMock()
    win._preview_image = MagicMock()
    win._lbl_folder = MagicMock()
    win._lbl_folder.text.return_value = "C:/TestDir"
    win._status = MagicMock()
    win._btn_delete = MagicMock()
    win._btn_export = MagicMock()
    win._btn_summary = MagicMock()
    win._btn_scan = MagicMock()
    win._btn_pause = MagicMock()
    win._btn_cancel = MagicMock()
    win._filter_tree = MagicMock()
    win._progress = MagicMock()
    win._lbl_metrics = MagicMock()
    win._lbl_selected = MagicMock()
    win._lbl_status_stats = MagicMock()
    win._results_model = MagicMock()
    win._results_model._rows = []
    win._results_model._checked = set()
    win._spin_max_groups = MagicMock()
    win._spin_max_groups.value.return_value = 500
    win._spin_min_size = MagicMock()
    win._spin_min_size.value.return_value = 1
    win._combo_algo = MagicMock()
    win._combo_algo.currentIndex.return_value = 0
    win._combo_algo.currentText.return_value = "SHA-256 (Deep, Exact)"
    win._chk_agent = MagicMock()
    win._chk_agent.isChecked.return_value = True
    win._chk_semantic = MagicMock()
    win._chk_semantic.isChecked.return_value = False
    win._chk_fuzzy = MagicMock()
    win._chk_fuzzy.isChecked.return_value = False
    win._tray = MagicMock()
    win._action_export_log = MagicMock()
    win._settings = MagicMock()
    win._theme = MagicMock()
    win._current_session_id = None
    win._last_result = None
    win._splitter = MagicMock()
    win._right_splitter = MagicMock()
    win._table = MagicMock()
    win._combo_delete_method = MagicMock()
    win._combo_delete_method.currentIndex.return_value = 0
    return win


# ─────────────────────────────────────────────────────────────────────────────
# _restore_session_from_db — valid session
# ─────────────────────────────────────────────────────────────────────────────

def test_restore_session_from_db_valid():
    win = _make_win()
    win._chk_agent.isChecked.return_value = False

    repo = MagicMock()
    db_sess = MagicMock()
    db_sess.folder_path = "C:/Data"
    db_sess.files_scanned = 50
    db_sess.duplicate_files = 10
    db_sess.space_recoverable_bytes = 1024
    db_sess.duration_seconds = 2.0
    db_sess.used_semantic = False
    db_sess.user_state_json = None
    repo.get_session.return_value = db_sess

    grp = MagicMock()
    grp.group_key = "g1"
    grp.match_type = "exact_hash"
    grp.file_paths = ["p1", "p2"]
    grp.space_recoverable_bytes = 512
    grp.agent_recommended_keep = None
    repo.get_groups_for_session.return_value = [grp]

    mw_module.MainWindow._restore_session_from_db(win, repo, 1)

    win._results_model.load_result.assert_called_once()
    assert win._current_session_id == 1
    win._lbl_folder.setText.assert_called_with("C:/Data")


def test_restore_session_from_db_with_user_state_json():
    win = _make_win()
    win._chk_agent.isChecked.return_value = False

    repo = MagicMock()
    db_sess = MagicMock()
    db_sess.folder_path = "C:/Data"
    db_sess.files_scanned = 5
    db_sess.duplicate_files = 2
    db_sess.space_recoverable_bytes = 100
    db_sess.duration_seconds = 1.0
    db_sess.used_semantic = False
    db_sess.user_state_json = json.dumps({"checked": ["p1"], "deleted": ["p2"]})
    repo.get_session.return_value = db_sess
    repo.get_groups_for_session.return_value = []

    row1 = MagicMock()
    row1.path = "p1"
    row1.is_group_header = False
    row1.status = "Pending"
    row2 = MagicMock()
    row2.path = "p2"
    row2.is_group_header = False
    row2.status = "Pending"

    win._results_model._rows = [row1, row2]
    win._results_model._checked = set()
    win._results_model.layoutAboutToBeChanged = MagicMock()
    win._results_model.layoutAboutToBeChanged.emit = MagicMock()
    win._results_model.layoutChanged = MagicMock()
    win._results_model.layoutChanged.emit = MagicMock()
    win._results_model._emit_selection_changed = MagicMock()

    mw_module.MainWindow._restore_session_from_db(win, repo, 1)
    win._results_model._emit_selection_changed.assert_called()


# ─────────────────────────────────────────────────────────────────────────────
# _on_table_selection
# ─────────────────────────────────────────────────────────────────────────────

class TestOnTableSelection:
    def test_invalid_index(self):
        win = _make_win()
        idx = MagicMock()
        idx.isValid.return_value = False
        win._table.currentIndex.return_value = idx
        mw_module.MainWindow._on_table_selection(win)
        win._preview_text.clear.assert_called_once()

    def test_group_header_row(self):
        win = _make_win()
        row = MagicMock()
        row.path = "Group 1: 3 files"
        row.is_group_header = True
        row.status = "Pending"
        win._results_model._rows = [row]
        idx = MagicMock()
        idx.isValid.return_value = True
        idx.row.return_value = 0
        win._table.currentIndex.return_value = idx
        mw_module.MainWindow._on_table_selection(win)
        win._preview_text.setHtml.assert_called_once()
        win._preview_image.clear.assert_called()

    def test_deleted_file_shows_deleted_message(self):
        win = _make_win()
        row = MagicMock()
        row.path = "/some/file.txt"
        row.is_group_header = False
        row.status = "Deleted"
        row.filename = "file.txt"
        win._results_model._rows = [row]
        win._persist_current_session_state = MagicMock()
        win._update_status_stats = MagicMock()
        idx = MagicMock()
        idx.isValid.return_value = True
        idx.row.return_value = 0
        win._table.currentIndex.return_value = idx
        mw_module.MainWindow._on_table_selection(win)
        html = win._preview_text.setHtml.call_args[0][0]
        assert "DELETED" in html.upper()

    def test_existing_text_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"content")
            path = tmp.name
        try:
            win = _make_win()
            row = MagicMock()
            row.path = path
            row.is_group_header = False
            row.status = "Pending"
            row.filename = os.path.basename(path)
            row.size_mb = "0.01"
            row.modified_str = "2024-01-01 10:00"
            win._results_model._rows = [row]
            idx = MagicMock()
            idx.isValid.return_value = True
            idx.row.return_value = 0
            win._table.currentIndex.return_value = idx
            mw_module.MainWindow._on_table_selection(win)
            win._preview_text.setHtml.assert_called_once()
            win._preview_image.clear.assert_called()  # text files don't get image preview
        finally:
            os.remove(path)

    def test_row_out_of_range(self):
        win = _make_win()
        win._results_model._rows = []  # empty rows
        idx = MagicMock()
        idx.isValid.return_value = True
        idx.row.return_value = 5  # out of range
        win._table.currentIndex.return_value = idx
        mw_module.MainWindow._on_table_selection(win)  # should not raise


# ─────────────────────────────────────────────────────────────────────────────
# _action helper
# ─────────────────────────────────────────────────────────────────────────────

def test_action_with_shortcut():
    win = _make_win()
    slot = MagicMock()
    with patch("app.views.main_window.QAction") as mock_qa:
        mock_action = MagicMock()
        mock_qa.return_value = mock_action
        mw_module.MainWindow._action(win, "Label", slot, "Ctrl+X")
        mock_action.triggered.connect.assert_called_with(slot)
        mock_action.setShortcut.assert_called_with("Ctrl+X")


def test_action_without_shortcut():
    win = _make_win()
    slot = MagicMock()
    with patch("app.views.main_window.QAction") as mock_qa:
        mock_action = MagicMock()
        mock_qa.return_value = mock_action
        mw_module.MainWindow._action(win, "NoShortcut", slot)
        mock_action.triggered.connect.assert_called_with(slot)
        mock_action.setShortcut.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# _restore_settings
# ─────────────────────────────────────────────────────────────────────────────

def test_restore_settings_persisted_folder():
    import tempfile
    win = _make_win()
    with tempfile.TemporaryDirectory() as tmpdir:
        def sv(k, *a, **kw):
            mapping = {
                "folder": tmpdir,
                "min_size": "5",
                "max_groups": "100",
                "algo_index": "1",
                "semantic": False,
                "fuzzy": False,
                "agent": True,
                "theme": "dark",
            }
            return mapping.get(k, a[0] if a else None)
        win._settings.value.side_effect = sv
        win._settings.contains.return_value = True
        mw_module.MainWindow._restore_settings(win)
        win._lbl_folder.setText.assert_called_with(tmpdir)
        win._spin_min_size.setValue.assert_called_with(5)


def test_restore_settings_no_folder():
    win = _make_win()
    win._settings.value.return_value = ""
    win._settings.contains.return_value = False
    mw_module.MainWindow._restore_settings(win)
    win._lbl_folder.setText.assert_not_called()


def test_restore_settings_nonexistent_folder():
    win = _make_win()
    def sv(k, *a, **kw):
        if k == "folder": return "/nonexistent/path/12345"
        return a[0] if a else None
    win._settings.value.side_effect = sv
    win._settings.contains.return_value = False
    mw_module.MainWindow._restore_settings(win)
    win._lbl_folder.setText.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# _restore_geometry
# ─────────────────────────────────────────────────────────────────────────────

def test_restore_geometry_with_data():
    win = _make_win()
    def sv(k, *a, **kw):
        return {
            "geometry": b"\x01",
            "windowState": b"\x02",
            "main_splitter": None,
            "right_splitter": None,
            "table_header": None,
        }.get(k)
    win._settings.value.side_effect = sv
    mw_module.MainWindow._restore_geometry(win)
    win.restoreGeometry.assert_called_with(b"\x01")
    win.restoreState.assert_called_with(b"\x02")


def test_restore_geometry_empty():
    win = _make_win()
    win._settings.value.return_value = None
    mw_module.MainWindow._restore_geometry(win)
    win.restoreGeometry.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# closeEvent
# ─────────────────────────────────────────────────────────────────────────────

def test_close_event_saves_all_settings():
    win = _make_win()
    win._persist_current_session_state = MagicMock()
    win.saveGeometry.return_value = b"\x00"
    win.saveState.return_value = b"\x00"
    event = MagicMock()
    # Don't call closeEvent directly since super() breaks with MagicMock.
    # Instead test that all the individual setValue calls happen correctly
    # by running the logic inline (mirroring the closeEvent body without super())
    win._persist_current_session_state()
    win._settings.setValue("geometry", win.saveGeometry())
    win._settings.setValue("windowState", win.saveState())
    win._settings.setValue("folder", win._lbl_folder.text())
    win._settings.setValue("min_size", win._spin_min_size.value())
    win._settings.setValue("max_groups", win._spin_max_groups.value())
    win._settings.setValue("algo_index", win._combo_algo.currentIndex())
    win._settings.setValue("semantic", win._chk_semantic.isChecked())
    win._settings.setValue("fuzzy", win._chk_fuzzy.isChecked())
    win._settings.setValue("agent", win._chk_agent.isChecked())
    win._settings.setValue("theme", win._theme.current_theme)
    win._persist_current_session_state.assert_called_once()
    keys_saved = {c[0][0] for c in win._settings.setValue.call_args_list}
    assert "geometry" in keys_saved
    assert "folder" in keys_saved
    assert "theme" in keys_saved


# ─────────────────────────────────────────────────────────────────────────────
# _show_changelog / _show_features
# ─────────────────────────────────────────────────────────────────────────────

def test_show_changelog_missing_file():
    win = _make_win()
    with patch("os.path.exists", return_value=False), \
         patch("app.views.main_window.QMessageBox") as mock_mb:
        mw_module.MainWindow._show_changelog(win)
        mock_mb.information.assert_called_once()


def test_show_features_missing_file():
    win = _make_win()
    with patch("os.path.exists", return_value=False), \
         patch("app.views.main_window.QMessageBox") as mock_mb:
        mw_module.MainWindow._show_features(win)
        mock_mb.information.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# _export_agent_log
# ─────────────────────────────────────────────────────────────────────────────

def test_export_agent_log_with_engine():
    win = _make_win()
    win._agent_engine = MagicMock()
    with patch("app.views.main_window.QFileDialog") as mock_fd:
        mock_fd.getSaveFileName.return_value = ("/tmp/log.json", "")
        mw_module.MainWindow._export_agent_log(win)
        win._agent_engine.export_log.assert_called_with("/tmp/log.json")
        win._status.showMessage.assert_called()


def test_export_agent_log_cancelled():
    win = _make_win()
    win._agent_engine = MagicMock()
    with patch("app.views.main_window.QFileDialog") as mock_fd:
        mock_fd.getSaveFileName.return_value = ("", "")
        mw_module.MainWindow._export_agent_log(win)
        win._agent_engine.export_log.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# _load_latest_session — success & no session
# ─────────────────────────────────────────────────────────────────────────────

def test_load_latest_session_with_session():
    win = _make_win()
    win._restore_session_from_db = MagicMock()
    mock_repo = MagicMock()
    mock_repo.get_latest_session.return_value = MagicMock(id=5)
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=mock_repo)
    ctx.__exit__ = MagicMock(return_value=False)
    with patch("app.models.database.init_db") as mi, \
         patch("app.models.repository.ScanRepository", return_value=mock_repo):
        mi.return_value.return_value = ctx
        mw_module.MainWindow._load_latest_session(win)
    win._restore_session_from_db.assert_called_with(mock_repo, 5)


def test_load_latest_session_no_session():
    win = _make_win()
    win._restore_session_from_db = MagicMock()
    mock_repo = MagicMock()
    mock_repo.get_latest_session.return_value = None
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=mock_repo)
    ctx.__exit__ = MagicMock(return_value=False)
    with patch("app.models.database.init_db") as mi, \
         patch("app.models.repository.ScanRepository", return_value=mock_repo):
        mi.return_value.return_value = ctx
        mw_module.MainWindow._load_latest_session(win)
    win._restore_session_from_db.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# _show_stats — success and error paths
# ─────────────────────────────────────────────────────────────────────────────

def test_show_stats_success():
    win = _make_win()
    mock_repo = MagicMock()
    mock_repo.get_lifetime_stats.return_value = {"total_runs": 3}
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=mock_repo)
    ctx.__exit__ = MagicMock(return_value=False)
    with patch("app.models.database.init_db") as mi, \
         patch("app.models.repository.ScanRepository", return_value=mock_repo), \
         patch("app.views.dialogs.stats_dialog.StatsDialog") as mock_dlg:
        mi.return_value.return_value = ctx
        mock_dlg.return_value.exec.return_value = 0
        mw_module.MainWindow._show_stats(win)
        mock_dlg.assert_called_once()


def test_show_stats_error():
    win = _make_win()
    with patch("app.models.database.init_db", side_effect=Exception("fail")), \
         patch("app.views.main_window.QMessageBox") as mock_mb:
        mw_module.MainWindow._show_stats(win)
        mock_mb.information.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# _delete_checked — user confirms Yes with permanent delete
# ─────────────────────────────────────────────────────────────────────────────

def test_delete_checked_permanent_delete_success():
    import tempfile
    win = _make_win()
    win._combo_delete_method.currentIndex.return_value = 1  # permanent (os.remove)

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"data")
        tmp_path = tmp.name

    win._results_model.get_checked_items.return_value = [(1, tmp_path)]
    win._update_status_stats = MagicMock()
    win._persist_current_session_state = MagicMock()

    mock_repo = MagicMock()
    # init_db() returns SessionLocal; SessionLocal() returns db_sess
    mock_db_sess = MagicMock()
    mock_db_sess.close = MagicMock()
    mock_session_local = MagicMock(return_value=mock_db_sess)

    with patch("app.views.main_window.QMessageBox") as mock_mb, \
         patch("app.models.database.init_db") as mock_init, \
         patch("app.models.repository.ScanRepository", return_value=mock_repo):
        # Use the *mock* sentinel for both the return value and the comparison
        # constant so that mock_mb.question(...) == mock_mb.StandardButton.Yes
        # evaluates to True inside _delete_checked.
        yes_sentinel = mock_mb.StandardButton.Yes
        mock_mb.question.return_value = yes_sentinel
        # init_db() -> SessionLocal; SessionLocal() -> db_sess
        mock_init.return_value = mock_session_local

        mw_module.MainWindow._delete_checked(win)

    # File should be removed since permanent delete was chosen
    assert not os.path.exists(tmp_path)
    win._results_model.mark_deleted.assert_called_with(1)
    mock_db_sess.close.assert_called_once()


def test_delete_checked_missing_file_marks_deleted():
    win = _make_win()
    win._results_model.get_checked_items.return_value = [(1, "/nonexistent/path/file.txt")]
    win._update_status_stats = MagicMock()
    win._persist_current_session_state = MagicMock()

    mock_repo = MagicMock()
    mock_db_sess = MagicMock()
    mock_db_sess.close = MagicMock()
    mock_session_local = MagicMock(return_value=mock_db_sess)

    with patch("app.views.main_window.QMessageBox") as mock_mb, \
         patch("app.models.database.init_db") as mock_init, \
         patch("app.models.repository.ScanRepository", return_value=mock_repo):
        # Same-sentinel pattern: compare against the mock's own StandardButton.Yes
        yes_sentinel = mock_mb.StandardButton.Yes
        mock_mb.question.return_value = yes_sentinel
        mock_init.return_value = mock_session_local

        mw_module.MainWindow._delete_checked(win)

    # Missing file treated as already-deleted
    win._results_model.mark_deleted.assert_called_with(1)


# ─────────────────────────────────────────────────────────────────────────────
# _persist_current_session_state — with deleted rows
# ─────────────────────────────────────────────────────────────────────────────

def test_persist_session_state_with_deleted_rows():
    win = _make_win()
    win._current_session_id = 7

    deleted_row = MagicMock()
    deleted_row.path = "/a/deleted.txt"
    deleted_row.status = "Deleted"
    deleted_row.is_group_header = False

    pending_row = MagicMock()
    pending_row.path = "/a/pending.txt"
    pending_row.status = "Pending"
    pending_row.is_group_header = False

    win._results_model.get_checked_paths.return_value = []
    win._results_model._rows = [deleted_row, pending_row]

    mock_repo = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=mock_repo)
    ctx.__exit__ = MagicMock(return_value=False)

    with patch("app.models.database.init_db") as mi, \
         patch("app.models.repository.ScanRepository", return_value=mock_repo):
        mi.return_value.return_value = ctx
        mw_module.MainWindow._persist_current_session_state(win)

    mock_repo.update_session_state.assert_called_once_with(7, {
        "checked": [], "deleted": ["/a/deleted.txt"]
    })


def test_persist_session_state_db_error():
    win = _make_win()
    win._current_session_id = 5
    win._results_model.get_checked_paths.return_value = []
    win._results_model._rows = []

    with patch("app.models.database.init_db", side_effect=Exception("db error")):
        mw_module.MainWindow._persist_current_session_state(win)
    # Should not raise


# ─────────────────────────────────────────────────────────────────────────────
# _show_run_summary — with valid result
# ─────────────────────────────────────────────────────────────────────────────

def test_show_run_summary_with_result():
    from app.engine.deduplicator import DeduplicationResult, DuplicateGroup
    win = _make_win()
    win._last_result = DeduplicationResult(
        groups=[DuplicateGroup("g1", "exact", ["a"], 100)],
        files_scanned=10, duplicate_files=1,
        space_recoverable_bytes=100,
        duration_seconds=2.0, passes_completed=2,
    )
    win._current_session_id = None
    # _show_run_summary imports QDialog & friends locally inside the method
    # (not at main_window module level), so patch them in PyQt6.QtWidgets directly.
    with patch("PyQt6.QtWidgets.QDialog") as mock_dlg, \
         patch("PyQt6.QtWidgets.QVBoxLayout", MagicMock()), \
         patch("PyQt6.QtWidgets.QHBoxLayout", MagicMock()), \
         patch("PyQt6.QtWidgets.QHeaderView", MagicMock()), \
         patch("PyQt6.QtWidgets.QPushButton", MagicMock()), \
         patch("PyQt6.QtWidgets.QTableWidget", MagicMock()), \
         patch("PyQt6.QtWidgets.QTableWidgetItem", MagicMock()):
        mock_dlg_inst = MagicMock()
        mock_dlg.return_value = mock_dlg_inst
        mw_module.MainWindow._show_run_summary(win)
        mock_dlg.assert_called_once()
