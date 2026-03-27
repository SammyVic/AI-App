"""
=============================================================================
app/viewmodels/results_viewmodel.py
=============================================================================
QAbstractTableModel ViewModel for the duplicate results table.
Bridges DeduplicationResult domain objects to the Qt view layer.
=============================================================================
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

from PyQt6.QtCore import (
    QAbstractTableModel, QModelIndex, Qt, pyqtSignal,
)
from PyQt6.QtGui import QColor

from app.engine.deduplicator import DeduplicationResult, DuplicateGroup
from app.agents.retention_agent import AgentDecision

# Column indices
COL_FILENAME = 0
COL_PATH = 1
COL_SIZE_MB = 2
COL_MODIFIED = 3
COL_MATCH_TYPE = 4
COL_STATUS = 5
COL_AI_REC = 6

_HEADERS = ["File Name", "Path", "Size (MB)", "Modified", "Match Type", "Status", "AI Recommendation"]


class _RowData:
    """Flattened row for a single file within a duplicate group."""
    __slots__ = (
        "group_key", "group_idx", "path", "filename", "size_bytes",
        "size_mb", "modified_str", "match_type", "status", "ai_rec",
        "is_group_header",
    )

    def __init__(
        self,
        group_key: str,
        group_idx: int,
        path: str,
        size_bytes: int,
        match_type: str,
        modified_at: float,
        status: str = "Pending",
        ai_rec: str = "",
        is_group_header: bool = False,
    ) -> None:
        self.group_key = group_key
        self.group_idx = group_idx
        self.path = path
        self.filename = os.path.basename(path)
        self.size_bytes = size_bytes
        self.size_mb = f"{size_bytes / (1024 * 1024):.2f}"
        self.modified_str = datetime.fromtimestamp(modified_at).strftime("%Y-%m-%d %H:%M") if modified_at else ""
        self.match_type = match_type
        self.status = status
        self.ai_rec = ai_rec
        self.is_group_header = is_group_header


class DuplicateTableModel(QAbstractTableModel):
    """
    Flat-table model for duplicate results.
    Group headers are special rows flagged by is_group_header.
    """

    selection_changed = pyqtSignal(int, int, int)   # (selected_files, selected_groups, total_size_bytes)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[_RowData] = []
        self._checked: set[int] = set()         # row indices that are checked
        self._group_header_rows: dict[str, int] = {}  # group_key -> row index

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_result(
        self,
        result: DeduplicationResult,
        decisions: Optional[dict[str, AgentDecision]] = None,
        max_groups: int = 0,
    ) -> None:
        """
        Populate the model from a DeduplicationResult.
        Optionally accepts agent decisions for the AI column.
        """
        self.beginResetModel()
        self._rows.clear()
        self._checked.clear()
        self._group_header_rows.clear()

        displayed = 0
        for group in result.groups:
            if max_groups > 0 and displayed >= max_groups:
                break

            decision = decisions.get(group.group_key) if decisions else None
            ai_keep = decision.recommended_keep if decision else ""
            conf = f" ({decision.confidence:.0%})" if decision else ""

            # --- Group header row ---
            header_idx = len(self._rows)
            self._group_header_rows[group.group_key] = header_idx
            self._rows.append(_RowData(
                group_key=group.group_key,
                group_idx=displayed,
                path=f"Group {displayed + 1}: {group.group_size} files — {group.match_type}",
                size_bytes=group.space_recoverable_bytes,
                match_type=group.match_type,
                modified_at=0,
                is_group_header=True,
            ))

            # --- File rows ---
            for path in group.file_paths:
                try:
                    stat = os.stat(path)
                    size = stat.st_size
                    mtime = stat.st_mtime
                except OSError:
                    size, mtime = 0, 0

                is_recommend = (path == ai_keep)
                ai_label = (f"✅ Keep{conf}" if is_recommend else "") if ai_keep else ""

                self._rows.append(_RowData(
                    group_key=group.group_key,
                    group_idx=displayed,
                    path=path,
                    size_bytes=size,
                    match_type=group.match_type,
                    modified_at=mtime,
                    ai_rec=ai_label,
                ))

            displayed += 1

        self.endResetModel()

    def mark_deleted(self, row: int) -> None:
        if 0 <= row < len(self._rows):
            self._rows[row].status = "Deleted"
            idx = self.index(row, COL_STATUS)
            self.dataChanged.emit(idx, idx)
            # Uncheck and clear selection state for this row
            if row in self._checked:
                self.check_row(row, False)

    def mark_group_deleted(self, group_key: str) -> None:
        first_row = -1
        last_row = -1
        for i, row in enumerate(self._rows):
            if row.group_key == group_key:
                row.status = "Deleted"
                if first_row == -1:
                    first_row = i
                last_row = i
                if i in self._checked:
                    self.check_row(i, False)
        if first_row != -1:
            idx_tl = self.index(first_row, 0)
            idx_br = self.index(last_row, self.columnCount() - 1)
            self.dataChanged.emit(idx_tl, idx_br)

    # ------------------------------------------------------------------
    # Checkbox support
    # ------------------------------------------------------------------

    def check_row(self, row: int, checked: bool) -> None:
        if checked:
            self._checked.add(row)
        else:
            self._checked.discard(row)
        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.CheckStateRole])
        
        # Notify that the group header's checkstate may have changed
        row_data = self._rows[row]
        if not row_data.is_group_header:
            header_idx = self._group_header_rows.get(row_data.group_key)
            if header_idx is not None:
                h_idx = self.index(header_idx, 0)
                self.dataChanged.emit(h_idx, h_idx, [Qt.ItemDataRole.CheckStateRole])
                
        self._emit_selection_changed()

    def get_checked_paths(self) -> list[str]:
        return [self._rows[r].path for r in sorted(self._checked)
                if not self._rows[r].is_group_header]

    def get_checked_items(self) -> list[tuple[int, str]]:
        return [(r, self._rows[r].path) for r in sorted(self._checked)
                if not self._rows[r].is_group_header]

    def _emit_selection_changed(self) -> None:
        checked_file_rows = [r for r in self._checked if not self._rows[r].is_group_header]
        group_keys = {self._rows[r].group_key for r in checked_file_rows}
        total_size = sum(self._rows[r].size_bytes for r in checked_file_rows)
        self.selection_changed.emit(len(checked_file_rows), len(group_keys), total_size)

    # ------------------------------------------------------------------
    # QAbstractTableModel interface
    # ------------------------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(_HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._rows):
            return None

        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if row.is_group_header:
                return row.path if col == COL_FILENAME else ""
            return {
                COL_FILENAME:  row.filename,
                COL_PATH:      row.path,
                COL_SIZE_MB:   row.size_mb,
                COL_MODIFIED:  row.modified_str,
                COL_MATCH_TYPE:row.match_type,
                COL_STATUS:    row.status,
                COL_AI_REC:    row.ai_rec,
            }.get(col, "")

        if role == Qt.ItemDataRole.CheckStateRole and col == COL_FILENAME:
            if row.is_group_header:
                group_key = row.group_key
                children = [i for i, r in enumerate(self._rows) if not r.is_group_header and r.group_key == group_key]
                if not children:
                    return Qt.CheckState.Unchecked
                checked_count = sum(1 for i in children if i in self._checked)
                if checked_count == 0:
                    return Qt.CheckState.Unchecked
                elif checked_count == len(children):
                    return Qt.CheckState.Checked
                else:
                    return Qt.CheckState.PartiallyChecked
            else:
                return Qt.CheckState.Checked if index.row() in self._checked else Qt.CheckState.Unchecked

        if role == Qt.ItemDataRole.BackgroundRole:
            if row.is_group_header:
                return QColor("#1e3a5f")  # dark blue header
            if row.status == "Deleted":
                return QColor("#3a3a3a")
            return None

        if role == Qt.ItemDataRole.ForegroundRole:
            if row.is_group_header:
                return QColor("#ffffff")
            if row.status == "Deleted":
                return QColor("#888888")
            return None

        if role == Qt.ItemDataRole.ToolTipRole:
            if not row.is_group_header:
                return row.path
            return None

        return None

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == COL_FILENAME:
            row_data = self._rows[index.row()]
            if row_data.status.lower() == "deleted":
                return False  # Prevent checking deleted items
                
            checked = (value == Qt.CheckState.Checked.value or value == Qt.CheckState.Checked)
            if row_data.is_group_header:
                group_key = row_data.group_key
                for i, r in enumerate(self._rows):
                    if not r.is_group_header and r.group_key == group_key:
                        if r.status.lower() != "deleted":
                            self.check_row(i, checked)
            else:
                self.check_row(index.row(), checked)
            return True
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        row = self._rows[index.row()] if index.row() < len(self._rows) else None
        if row and index.column() == COL_FILENAME:
            if row.status.lower() != "deleted":
                base |= Qt.ItemFlag.ItemIsUserCheckable
        return base
