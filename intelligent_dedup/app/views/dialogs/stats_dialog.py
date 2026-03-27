"""
=============================================================================
app/views/dialogs/stats_dialog.py
=============================================================================
Lifetime Statistics Dialog — reads from SQLite via repository.
Replaces the legacy lifetime_stats.json viewer.
=============================================================================
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt


def _fmt_gb(b: int) -> str:
    return f"{b / (1024 ** 3):.2f} GB"


class StatsDialog(QDialog):
    def __init__(self, parent=None, stats: dict = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📊 Lifetime Statistics")
        self.setModal(True)
        self.resize(500, 450)
        stats = stats or {}

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("<h2>Application Impact Report</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.table = QTableWidget(10, 2)
        self.table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        def _fmt_mb(b: int) -> str:
            return f"{b / (1024 ** 2):.2f} MB"

        items = [
            ("Total Scans Run", f"{stats.get('total_runs', 0):,}"),
            ("Total Files Scanned", f"{stats.get('total_files_scanned', 0):,}"),
            ("Duplicate Groups Found", f"{stats.get('total_duplicate_groups', 0):,}"),
            ("Duplicate Files Found", f"{stats.get('total_duplicate_files', 0):,}"),
            ("Files Deleted", f"{stats.get('total_files_deleted', 0):,}"),
            ("Delete Operations", f"{stats.get('total_delete_operations', 0):,}"),
            ("Total Space Freed", _fmt_gb(stats.get("total_space_freed_bytes", 0))),
            ("Last Run Date", str(stats.get("last_run_date", "Never"))),
            ("Last Run Files Deleted", f"{stats.get('last_run_deleted', 0):,}"),
            ("Last Run Space Freed", _fmt_mb(stats.get("last_run_space", 0))),
        ]

        for i, (metric, val) in enumerate(items):
            self.table.setItem(i, 0, QTableWidgetItem(metric))
            self.table.setItem(i, 1, QTableWidgetItem(val))

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 200)
        self.table.setColumnWidth(1, 250)

        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(btn)
        layout.addLayout(btn_row)
