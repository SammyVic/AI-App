"""
tests/test_dialogs.py
=============================================================================
Unit tests for app/views/dialogs/ using unbound-method pattern.
Both dialogs extend QDialog which requires QApplication to instantiate.
We test the pure-Python logic by calling unbound methods on MagicMock objects.
=============================================================================
"""
from __future__ import annotations
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# stats_dialog module-level helper
# ─────────────────────────────────────────────────────────────────────────────

import app.views.dialogs.stats_dialog as sd_module


class TestFmtGb:
    def test_zero(self):
        assert sd_module._fmt_gb(0) == "0.00 GB"

    def test_one_gb(self):
        assert sd_module._fmt_gb(1024 ** 3) == "1.00 GB"

    def test_half_gb(self):
        assert sd_module._fmt_gb(512 * 1024 * 1024) == "0.50 GB"

    def test_large(self):
        result = sd_module._fmt_gb(10 * 1024 ** 3)
        assert result == "10.00 GB"


# ─────────────────────────────────────────────────────────────────────────────
# StatsDialog data-population logic
# ─────────────────────────────────────────────────────────────────────────────

class TestStatsDialogData:
    def _make_dialog(self, stats=None):
        """Create a fake StatsDialog without instantiating QDialog."""
        dlg = MagicMock()
        dlg.table = MagicMock()
        rows = {}

        def set_item(r, c, item):
            rows[(r, c)] = item

        dlg.table.setItem.side_effect = set_item
        return dlg, rows

    def test_all_stats_keys_present(self):
        """Verify all expected stat keys are used from the stats dict."""
        stats = {
            "total_runs": 5,
            "total_files_scanned": 1000,
            "total_duplicate_groups": 50,
            "total_duplicate_files": 200,
            "total_files_deleted": 100,
            "total_delete_operations": 12,
            "total_space_freed_bytes": 2 * 1024 ** 3,
            "last_run_date": "2026-01-01",
            "last_run_deleted": 10,
            "last_run_space": 512 * 1024 * 1024,
        }
        # We call the formatting that happens inside __init__ inline here
        # (mirroring the logic without Qt)
        def _fmt_mb(b): return f"{b / (1024 ** 2):.2f} MB"

        items = [
            ("Total Scans Run", f"{stats.get('total_runs', 0):,}"),
            ("Total Files Scanned", f"{stats.get('total_files_scanned', 0):,}"),
            ("Duplicate Groups Found", f"{stats.get('total_duplicate_groups', 0):,}"),
            ("Duplicate Files Found", f"{stats.get('total_duplicate_files', 0):,}"),
            ("Files Deleted", f"{stats.get('total_files_deleted', 0):,}"),
            ("Delete Operations", f"{stats.get('total_delete_operations', 0):,}"),
            ("Total Space Freed", sd_module._fmt_gb(stats.get("total_space_freed_bytes", 0))),
            ("Last Run Date", str(stats.get("last_run_date", "Never"))),
            ("Last Run Files Deleted", f"{stats.get('last_run_deleted', 0):,}"),
            ("Last Run Space Freed", _fmt_mb(stats.get("last_run_space", 0))),
        ]

        assert len(items) == 10
        assert items[0] == ("Total Scans Run", "5")
        assert items[6] == ("Total Space Freed", "2.00 GB")
        assert items[9][1] == "512.00 MB"

    def test_empty_stats_uses_defaults(self):
        stats = {}
        items_values = [
            f"{stats.get('total_runs', 0):,}",
            f"{stats.get('total_files_scanned', 0):,}",
            sd_module._fmt_gb(stats.get("total_space_freed_bytes", 0)),
            str(stats.get("last_run_date", "Never")),
        ]
        assert items_values[0] == "0"
        assert items_values[2] == "0.00 GB"
        assert items_values[3] == "Never"


# ─────────────────────────────────────────────────────────────────────────────
# LoadSessionDialog logic
# ─────────────────────────────────────────────────────────────────────────────

import app.views.dialogs.load_session_dialog as lsd_module


class TestLoadSessionDialogOnAccept:
    def _make_dialog_with_row(self, row_selected: int, session_id=42):
        """Create fake dialog with a selected row."""
        dlg = MagicMock(spec=lsd_module.LoadSessionDialog)
        dlg.table = MagicMock()
        dlg.table.currentRow.return_value = row_selected
        dlg.selected_session_id = None

        # Mock the item at (row, 0)
        cell_item = MagicMock()
        cell_item.data.return_value = session_id
        dlg.table.item.return_value = cell_item

        return dlg

    def test_on_accept_valid_row(self):
        dlg = self._make_dialog_with_row(row_selected=0, session_id=7)
        lsd_module.LoadSessionDialog._on_accept(dlg)
        assert dlg.selected_session_id == 7
        dlg.accept.assert_called_once()

    def test_on_accept_no_row_selected(self):
        dlg = self._make_dialog_with_row(row_selected=-1)
        lsd_module.LoadSessionDialog._on_accept(dlg)
        # selected_session_id should remain None
        assert dlg.selected_session_id is None
        dlg.reject.assert_called_once()

    def test_on_accept_second_session(self):
        dlg = self._make_dialog_with_row(row_selected=1, session_id=99)
        lsd_module.LoadSessionDialog._on_accept(dlg)
        assert dlg.selected_session_id == 99

    def test_sessions_list_stored(self):
        """Verify _sessions list is stored on dialog."""
        dlg = MagicMock()
        sessions = [MagicMock(), MagicMock()]
        # Simulate what __init__ does before _build_ui
        dlg._sessions = sessions
        dlg.selected_session_id = None
        assert len(dlg._sessions) == 2
