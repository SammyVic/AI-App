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
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt


def _fmt_gb(b: int) -> str:
    return f"{b / (1024 ** 3):.2f} GB"


class StatsDialog(QDialog):
    def __init__(self, parent=None, stats: dict = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📊 Lifetime Statistics")
        self.setModal(True)
        self.resize(420, 300)
        stats = stats or {}

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("<h2>Application Impact Report</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        for label, value in [
            ("Total Scans Run", f"{stats.get('total_runs', 0):,}"),
            ("Total Files Scanned", f"{stats.get('total_files_scanned', 0):,}"),
            ("Duplicate Groups Found", f"{stats.get('total_duplicate_groups', 0):,}"),
            ("Duplicate Files Found", f"{stats.get('total_duplicate_files', 0):,}"),
            ("Files Deleted", f"{stats.get('total_files_deleted', 0):,}"),
            ("Delete Operations", f"{stats.get('total_delete_operations', 0):,}"),
            ("Total Space Freed", _fmt_gb(stats.get("total_space_freed_bytes", 0))),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"<b>{label}:</b>"))
            row.addStretch()
            row.addWidget(QLabel(value))
            layout.addLayout(row)

        layout.addStretch()
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
