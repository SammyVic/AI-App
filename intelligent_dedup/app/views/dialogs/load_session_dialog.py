"""
=============================================================================
app/views/dialogs/load_session_dialog.py
=============================================================================
Dialog to select and restore a previous scan session from the SQLite database.
=============================================================================
"""

from typing import Optional
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt

class LoadSessionDialog(QDialog):
    def __init__(self, parent, sessions: list) -> None:
        super().__init__(parent)
        self.setWindowTitle("Load Previous Session")
        self.resize(800, 400)
        self.selected_session_id: Optional[int] = None
        self._sessions = sessions
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget(len(self._sessions), 5)
        self.table.setHorizontalHeaderLabels([
            "ID", "Date", "Folder", "Files Scanned", "Duplicate Groups"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 350)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 120)
        
        for row, sess in enumerate(self._sessions):
            self.table.setItem(row, 0, QTableWidgetItem(str(sess.id)))
            self.table.setItem(row, 1, QTableWidgetItem(sess.started_at_human()))
            self.table.setItem(row, 2, QTableWidgetItem(sess.folder_path))
            self.table.setItem(row, 3, QTableWidgetItem(f"{sess.files_scanned:,}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{sess.duplicate_groups:,}"))
            
            # Store ID in user data of the first column
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, sess.id)
            
        self.table.itemDoubleClicked.connect(self._on_accept)

        btn_row = QHBoxLayout()
        self.btn_load = QPushButton("Load Session")
        self.btn_load.clicked.connect(self._on_accept)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_row.addStretch()
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_load)
        
        layout.addWidget(self.table)
        layout.addLayout(btn_row)

    def _on_accept(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            self.selected_session_id = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
        else:
            self.reject()
