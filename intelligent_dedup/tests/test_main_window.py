"""
tests/test_main_window.py
=============================================================================
Unit tests for app/views/main_window.py.

Strategy: Rather than instantiating MainWindow (which requires a live
QApplication + display), we create a lightweight FakeWindow that inherits from
MainWindow but overrides __init__ with a no-op, then manually attach all the
mocked widget attributes the tested method needs.

This lets us call unbound methods directly, bypassing Qt entirely, while still
counting toward code coverage for the real module.
=============================================================================
"""

from __future__ import annotations

import os
import types
import json
from unittest.mock import MagicMock, patch, call

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Minimal fake window fixture
# ─────────────────────────────────────────────────────────────────────────────

import app.views.main_window as mw_module


def _make_win() -> MagicMock:
    """
    Return a MagicMock that masquerades as a MainWindow instance.
    Unbound methods from MainWindow can be called as:
        mw_module.MainWindow._some_method(win, ...)
    All Qt widgets are pre-wired as MagicMocks.
    """
    win = MagicMock()
    # Attributes touched by the methods under test
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
# FILE_CATEGORIES module-level constant
# ─────────────────────────────────────────────────────────────────────────────

def test_file_categories_structure():
    cats = mw_module.FILE_CATEGORIES
    assert "Images" in cats
    assert "Documents" in cats
    assert "Video" in cats
    assert "Audio" in cats
    assert "Archives" in cats
    assert "Code/Web" in cats
    assert ".jpg" in cats["Images"]
    assert ".pdf" in cats["Documents"]


# ─────────────────────────────────────────────────────────────────────────────
# _render_agent_panel
# ─────────────────────────────────────────────────────────────────────────────

class TestRenderAgentPanel:
    def test_high_confidence(self):
        win = _make_win()
        decision = MagicMock()
        decision.confidence = 0.90
        decision.recommended_keep = "/home/user/file.jpg"
        decision.scores = [MagicMock(flags=["Canonical folder"])]
        mw_module.MainWindow._render_agent_panel(win, {"grp1": decision})
        html = win._agent_text.setHtml.call_args[0][0]
        assert "Group grp1" in html
        assert "90%" in html
        assert "#4caf50" in html  # green for >=80%

    def test_medium_confidence(self):
        win = _make_win()
        decision = MagicMock()
        decision.confidence = 0.65
        decision.recommended_keep = "/home/user/file.jpg"
        decision.scores = [MagicMock(flags=[])]
        mw_module.MainWindow._render_agent_panel(win, {"grp2": decision})
        html = win._agent_text.setHtml.call_args[0][0]
        assert "#ff9800" in html  # orange for 50-79%

    def test_low_confidence(self):
        win = _make_win()
        decision = MagicMock()
        decision.confidence = 0.30
        decision.recommended_keep = "/home/user/file.jpg"
        decision.scores = [MagicMock(flags=[])]
        mw_module.MainWindow._render_agent_panel(win, {"grp3": decision})
        html = win._agent_text.setHtml.call_args[0][0]
        assert "#f44336" in html  # red for <50%

    def test_empty_decisions(self):
        win = _make_win()
        mw_module.MainWindow._render_agent_panel(win, {})
        html = win._agent_text.setHtml.call_args[0][0]
        assert "AI Retention Recommendations" in html

    def test_many_decisions_capped_at_50(self):
        win = _make_win()
        decisions = {}
        for i in range(100):
            d = MagicMock()
            d.confidence = 0.8
            d.recommended_keep = f"/f{i}"
            d.scores = [MagicMock(flags=[])]
            decisions[f"g{i}"] = d
        mw_module.MainWindow._render_agent_panel(win, decisions)
        html = win._agent_text.setHtml.call_args[0][0]
        # Only first 50 should be shown
        assert "g49" in html
        assert "g50" not in html


# ─────────────────────────────────────────────────────────────────────────────
# _update_selection_metrics
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdateSelectionMetrics:
    def test_nonzero_selection(self):
        win = _make_win()
        mw_module.MainWindow._update_selection_metrics(win, 3, 2, 2 * 1024 * 1024)
        text = win._lbl_selected.setText.call_args[0][0]
        assert "3 files" in text
        assert "2 groups" in text
        assert "2.00 MB" in text
        win._btn_delete.setEnabled.assert_called_with(True)

    def test_zero_selection_disables_button(self):
        win = _make_win()
        mw_module.MainWindow._update_selection_metrics(win, 0, 0, 0)
        win._btn_delete.setEnabled.assert_called_with(False)

    def test_large_size_formatting(self):
        win = _make_win()
        mw_module.MainWindow._update_selection_metrics(win, 1, 1, 1024 * 1024 * 1024)  # 1 GB
        text = win._lbl_selected.setText.call_args[0][0]
        assert "1024.00 MB" in text


# ─────────────────────────────────────────────────────────────────────────────
# _on_scanning_state
# ─────────────────────────────────────────────────────────────────────────────

class TestOnScanningState:
    def test_scanning_true(self):
        win = _make_win()
        mw_module.MainWindow._on_scanning_state(win, True)
        win._btn_scan.setEnabled.assert_called_with(False)
        win._btn_pause.setEnabled.assert_called_with(True)
        win._btn_cancel.setEnabled.assert_called_with(True)
        win._filter_tree.setEnabled.assert_called_with(False)
        win._progress.setVisible.assert_called_with(True)

    def test_scanning_false(self):
        win = _make_win()
        mw_module.MainWindow._on_scanning_state(win, False)
        win._btn_scan.setEnabled.assert_called_with(True)
        win._btn_pause.setEnabled.assert_called_with(False)
        win._btn_cancel.setEnabled.assert_called_with(False)
        win._filter_tree.setEnabled.assert_called_with(True)
        win._progress.setVisible.assert_called_with(False)


# ─────────────────────────────────────────────────────────────────────────────
# _on_progress
# ─────────────────────────────────────────────────────────────────────────────

class TestOnProgress:
    def test_with_total(self):
        win = _make_win()
        win._scan_start_time = 0  # let elapsed calc be non-zero
        mw_module.MainWindow._on_progress(win, 2, 50, 200, 5, "01:30")
        win._progress.setRange.assert_called_with(0, 200)
        win._progress.setValue.assert_called_with(50)
        text = win._lbl_metrics.setText.call_args[0][0]
        assert "Pass 2/3" in text
        assert "50" in text
        assert "5" in text

    def test_zero_total_indeterminate(self):
        win = _make_win()
        win._scan_start_time = 0
        mw_module.MainWindow._on_progress(win, 1, 0, 0, 0, "")
        win._progress.setRange.assert_called_with(0, 0)


# ─────────────────────────────────────────────────────────────────────────────
# _update_status_stats
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdateStatusStats:
    def test_normal_stats(self):
        win = _make_win()
        mock_sess = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_lifetime_stats.return_value = {
            "total_files_deleted": 42,
            "total_space_freed_bytes": 100 * 1024 * 1024,
        }
        mock_sess.__enter__ = MagicMock(return_value=mock_repo)
        mock_sess.__exit__ = MagicMock(return_value=False)

        with patch("app.models.database.init_db") as mock_init, \
             patch("app.models.repository.ScanRepository", return_value=mock_repo):
            mock_init.return_value.return_value = mock_sess
            mw_module.MainWindow._update_status_stats(win)

        win._lbl_status_stats.setText.assert_called_once()
        text = win._lbl_status_stats.setText.call_args[0][0]
        assert "42" in text
        assert "100.00 MB" in text

    def test_db_error_does_not_raise(self):
        win = _make_win()
        with patch("app.models.database.init_db", side_effect=Exception("db offline")):
            mw_module.MainWindow._update_status_stats(win)
        # Should not raise; label may or may not be updated but no crash.

    def test_missing_label_attr_skips(self):
        win = _make_win()
        del win._lbl_status_stats  # simulate attribute not yet created
        # Should return early without error
        mw_module.MainWindow._update_status_stats(win)


# ─────────────────────────────────────────────────────────────────────────────
# _on_scan_finished
# ─────────────────────────────────────────────────────────────────────────────

class TestOnScanFinished:
    def _make_result(self):
        from app.engine.deduplicator import DeduplicationResult, DuplicateGroup
        return DeduplicationResult(
            groups=[DuplicateGroup("g1", "exact_hash", ["p1", "p2"], 2048)],
            files_scanned=10, duplicate_files=2,
            space_recoverable_bytes=2048,
            duration_seconds=1.5, passes_completed=2,
        )

    def test_saves_to_db_and_loads_model(self):
        win = _make_win()
        result = self._make_result()
        mock_repo = MagicMock()
        mock_db_sess = MagicMock()
        mock_db_sess.id = 99
        mock_repo.create_session.return_value = mock_db_sess
        mock_repo.get_groups_for_session.return_value = []
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_repo)
        ctx.__exit__ = MagicMock(return_value=False)

        with patch("app.models.database.init_db") as mock_init, \
             patch("app.models.repository.ScanRepository", return_value=mock_repo), \
             patch("app.agents.reasoning_engine.ReasoningEngine") as mock_eng_cls:
            mock_init.return_value.return_value = ctx
            mock_eng = mock_eng_cls.return_value
            mock_eng.process.return_value = {}
            mw_module.MainWindow._on_scan_finished(win, result)

        win._results_model.load_result.assert_called_once()
        win._btn_delete.setEnabled.assert_called_with(True)
        win._btn_export.setEnabled.assert_called_with(True)

    def test_agent_disabled_skips_reasoning(self):
        win = _make_win()
        win._chk_agent.isChecked.return_value = False
        result = self._make_result()
        mock_repo = MagicMock()
        mock_db_sess = MagicMock()
        mock_db_sess.id = 1
        mock_repo.create_session.return_value = mock_db_sess
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_repo)
        ctx.__exit__ = MagicMock(return_value=False)

        with patch("app.models.database.init_db") as mock_init, \
             patch("app.models.repository.ScanRepository", return_value=mock_repo), \
             patch("app.agents.reasoning_engine.ReasoningEngine") as mock_eng_cls:
            mock_init.return_value.return_value = ctx
            mw_module.MainWindow._on_scan_finished(win, result)
            mock_eng_cls.assert_not_called()

    def test_db_failure_still_loads_model(self):
        win = _make_win()
        result = self._make_result()
        with patch("app.models.database.init_db", side_effect=Exception("DB down")):
            mw_module.MainWindow._on_scan_finished(win, result)
        # Should still call load_result despite DB failure
        win._results_model.load_result.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# _start_scan validation
# ─────────────────────────────────────────────────────────────────────────────

class TestStartScan:
    def test_invalid_folder_shows_warning(self):
        win = _make_win()
        win._lbl_folder.text.return_value = "/nonexistent/path/12345"
        with patch("app.views.main_window.QMessageBox") as mock_mb:
            mw_module.MainWindow._start_scan(win)
            mock_mb.warning.assert_called_once()

    def test_no_extensions_shows_warning(self):
        win = _make_win()
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            win._lbl_folder.text.return_value = tmpdir
            win._get_selected_extensions = MagicMock(return_value=set())
            with patch("app.views.main_window.QMessageBox") as mock_mb:
                mw_module.MainWindow._start_scan(win)
                mock_mb.warning.assert_called_once()

    def test_valid_folder_starts_scan(self):
        win = _make_win()
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            win._lbl_folder.text.return_value = tmpdir
            win._get_selected_extensions = MagicMock(return_value={".txt"})
            win._persist_current_session_state = MagicMock()
            win._update_status_stats = MagicMock()
            win._results_model.beginResetModel = MagicMock()
            win._results_model.endResetModel = MagicMock()
            win._results_model._rows = []
            with patch("app.views.main_window.QMessageBox"):
                mw_module.MainWindow._start_scan(win)
            win._scan_vm.start_scan.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# _apply_search_filter (placeholder)
# ─────────────────────────────────────────────────────────────────────────────

def test_apply_search_filter_is_noop():
    win = _make_win()
    # Should not raise
    mw_module.MainWindow._apply_search_filter(win)


# ─────────────────────────────────────────────────────────────────────────────
# _apply_profile (placeholder)
# ─────────────────────────────────────────────────────────────────────────────

def test_apply_profile_is_noop():
    win = _make_win()
    mw_module.MainWindow._apply_profile(win)


# ─────────────────────────────────────────────────────────────────────────────
# _persist_current_session_state
# ─────────────────────────────────────────────────────────────────────────────

class TestPersistCurrentSessionState:
    def test_no_session_id_returns_early(self):
        win = _make_win()
        win._current_session_id = None
        with patch("app.models.database.init_db") as mock_init:
            mw_module.MainWindow._persist_current_session_state(win)
            mock_init.assert_not_called()

    def test_with_session_id_calls_repo(self):
        win = _make_win()
        win._current_session_id = 7
        mock_row = MagicMock()
        mock_row.path = "/a/b.txt"
        mock_row.status = "Pending"
        mock_row.is_group_header = False
        win._results_model.get_checked_paths.return_value = ["/a/b.txt"]
        win._results_model._rows = [mock_row]
        mock_repo = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_repo)
        ctx.__exit__ = MagicMock(return_value=False)
        with patch("app.models.database.init_db") as mock_init, \
             patch("app.models.repository.ScanRepository", return_value=mock_repo):
            mock_init.return_value.return_value = ctx
            mw_module.MainWindow._persist_current_session_state(win)
        mock_repo.update_session_state.assert_called_once_with(7, {
            "checked": ["/a/b.txt"], "deleted": []
        })


# ─────────────────────────────────────────────────────────────────────────────
# _drop_event
# ─────────────────────────────────────────────────────────────────────────────

def test_drop_event_sets_folder():
    win = _make_win()
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        event = MagicMock()
        event.mimeData.return_value.urls.return_value = [MagicMock()]
        event.mimeData().urls()[0].toLocalFile.return_value = tmpdir
        mw_module.MainWindow._drop_event(win, event)
        win._lbl_folder.setText.assert_called_with(tmpdir)


def test_drop_event_ignores_non_dir():
    win = _make_win()
    event = MagicMock()
    event.mimeData.return_value.urls.return_value = [MagicMock()]
    event.mimeData().urls()[0].toLocalFile.return_value = "/nonexistent/file.txt"
    mw_module.MainWindow._drop_event(win, event)
    win._lbl_folder.setText.assert_not_called()


def test_drop_event_empty_urls():
    win = _make_win()
    event = MagicMock()
    event.mimeData.return_value.urls.return_value = []
    mw_module.MainWindow._drop_event(win, event)
    win._lbl_folder.setText.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# _drag_enter
# ─────────────────────────────────────────────────────────────────────────────

def test_drag_enter_accepts_urls():
    win = _make_win()
    event = MagicMock()
    event.mimeData().hasUrls.return_value = True
    mw_module.MainWindow._drag_enter(win, event)
    event.accept.assert_called_once()


def test_drag_enter_ignores_non_urls():
    win = _make_win()
    event = MagicMock()
    event.mimeData().hasUrls.return_value = False
    mw_module.MainWindow._drag_enter(win, event)
    event.accept.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# _show_run_summary — early return when no result
# ─────────────────────────────────────────────────────────────────────────────

def test_show_run_summary_no_result():
    win = _make_win()
    win._last_result = None
    # Should return early — no dialog opened
    result = mw_module.MainWindow._show_run_summary(win)
    assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# _export_agent_log — no engine present
# ─────────────────────────────────────────────────────────────────────────────

def test_export_agent_log_no_engine():
    win = _make_win()
    # No _agent_engine attribute -> should return silently
    with patch("app.views.main_window.QFileDialog") as mock_fd:
        mock_fd.getSaveFileName.return_value = ("/tmp/log.json", "")
        # _agent_engine not set, so nothing should be exported
        mw_module.MainWindow._export_agent_log(win)


# ─────────────────────────────────────────────────────────────────────────────
# _load_latest_session — db error is swallowed
# ─────────────────────────────────────────────────────────────────────────────

def test_load_latest_session_db_error():
    win = _make_win()
    with patch("app.models.database.init_db", side_effect=Exception("no db")):
        mw_module.MainWindow._load_latest_session(win)
    # No exception should propagate


# ─────────────────────────────────────────────────────────────────────────────
# _show_stats — db error shows message box
# ─────────────────────────────────────────────────────────────────────────────

def test_show_stats_db_error():
    win = _make_win()
    with patch("app.models.database.init_db", side_effect=Exception("stats fail")), \
         patch("app.views.main_window.QMessageBox") as mock_mb:
        mw_module.MainWindow._show_stats(win)
        mock_mb.information.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# _on_scan_error
# ─────────────────────────────────────────────────────────────────────────────

def test_on_scan_error_shows_critical():
    win = _make_win()
    with patch("app.views.main_window.QMessageBox") as mock_mb:
        mw_module.MainWindow._on_scan_error(win, "Something broke")
        mock_mb.critical.assert_called_once()
        args = mock_mb.critical.call_args[0]
        assert "Something broke" in args[2]


# ─────────────────────────────────────────────────────────────────────────────
# _export_csv — normal path
# ─────────────────────────────────────────────────────────────────────────────

def test_export_csv_writes_file():
    import tempfile, csv, os
    win = _make_win()

    # Build a fake row
    fake_row = MagicMock()
    fake_row.is_group_header = False
    fake_row.group_key = "g1"
    fake_row.filename = "file.txt"
    fake_row.path = "/a/file.txt"
    fake_row.size_mb = "0.01"
    fake_row.match_type = "exact_hash"
    fake_row.status = "Pending"

    # model with 1 data row
    win._results_model.rowCount.return_value = 1
    win._results_model._rows = [fake_row]

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with patch("app.views.main_window.QFileDialog") as mock_fd:
            mock_fd.getSaveFileName.return_value = (tmp_path, "")
            mw_module.MainWindow._export_csv(win)

        with open(tmp_path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["Group", "Filename", "Path", "Size (MB)", "Match Type", "Status"]
        assert "file.txt" in rows[1]
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_export_csv_cancelled_returns():
    win = _make_win()
    with patch("app.views.main_window.QFileDialog") as mock_fd:
        mock_fd.getSaveFileName.return_value = ("", "")
        mw_module.MainWindow._export_csv(win)
    # No model methods called
    win._results_model.rowCount.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# _toggle_panel
# ─────────────────────────────────────────────────────────────────────────────

def test_toggle_panel_visible_to_hidden():
    win = _make_win()
    widget = MagicMock()
    widget.isVisible.return_value = True
    win._splitter.widget.return_value = widget
    mw_module.MainWindow._toggle_panel(win, 0)
    widget.setVisible.assert_called_with(False)


def test_toggle_panel_hidden_to_visible():
    win = _make_win()
    widget = MagicMock()
    widget.isVisible.return_value = False
    win._splitter.widget.return_value = widget
    mw_module.MainWindow._toggle_panel(win, 0)
    widget.setVisible.assert_called_with(True)


def test_toggle_panel_no_widget():
    win = _make_win()
    win._splitter.widget.return_value = None
    mw_module.MainWindow._toggle_panel(win, 99)  # should not raise


# ─────────────────────────────────────────────────────────────────────────────
# _delete_checked — nothing checked
# ─────────────────────────────────────────────────────────────────────────────

def test_delete_checked_nothing_checked():
    win = _make_win()
    win._results_model.get_checked_items.return_value = []
    with patch("app.views.main_window.QMessageBox") as mock_mb:
        mw_module.MainWindow._delete_checked(win)
        mock_mb.information.assert_called_once()


def test_delete_checked_user_cancels():
    win = _make_win()
    win._results_model.get_checked_items.return_value = [(1, "/a/file.txt")]
    with patch("app.views.main_window.QMessageBox") as mock_mb:
        from PyQt6.QtWidgets import QMessageBox as RealQMB
        mock_mb.question.return_value = RealQMB.StandardButton.No
        with patch("app.models.database.init_db"):
            mw_module.MainWindow._delete_checked(win)
        # model.mark_deleted should NOT be called
        win._results_model.mark_deleted.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# _restore_session_from_db — empty session
# ─────────────────────────────────────────────────────────────────────────────

def test_restore_session_from_db_missing_session():
    win = _make_win()
    repo = MagicMock()
    repo.get_session.return_value = None  # session not found
    mw_module.MainWindow._restore_session_from_db(win, repo, 999)
    win._results_model.load_result.assert_not_called()
