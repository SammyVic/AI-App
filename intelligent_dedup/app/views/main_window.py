"""
=============================================================================
app/views/main_window.py
=============================================================================
Pure Qt View — Main Application Window (MVVM: zero business logic here).

Binds to ScanViewModel, DuplicateTableModel, and ReasoningEngine.
All user actions delegate to ViewModel methods.
=============================================================================
"""

from __future__ import annotations

import os
import logging
from pathlib import Path

from PyQt6.QtCore import Qt, QSettings, QTimer, pyqtSlot
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QProgressBar,
    QPushButton, QSizePolicy, QSpinBox, QSplitter, QStatusBar,
    QSystemTrayIcon, QTableView, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from app.views.theme_manager import ThemeManager
from app.viewmodels.scan_viewmodel import ScanViewModel
from app.viewmodels.results_viewmodel import DuplicateTableModel
from app.engine.scanner import SYSTEM_EXCLUSIONS
from app.engine.deduplicator import DeduplicationResult

logger = logging.getLogger(__name__)

# Default file categories
FILE_CATEGORIES: dict[str, list[str]] = {
    "Images":     [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"],
    "Documents":  [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".csv", ".log"],
    "Video":      [".mp4", ".avi", ".mkv", ".mov", ".mpeg", ".wmv"],
    "Audio":      [".mp3", ".wav", ".flac", ".aac", ".ogg"],
    "Archives":   [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Code/Web":   [".html", ".htm", ".css", ".js", ".json", ".xml", ".py", ".ts"],
}


class MainWindow(QMainWindow):
    """
    Enterprise-grade main window. Three-pane layout:
      Left   — scan controls & filters
      Centre — results table (QTableView + QAbstractTableModel)
      Right  — AI agent recommendations panel
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Intelligent Dedup — Enterprise Edition v2.0")
        self.resize(1500, 900)

        # --- Sub-systems ---
        self._theme = ThemeManager()
        self._scan_vm = ScanViewModel(self)
        self._results_model = DuplicateTableModel(self)
        self._settings = QSettings("IntelligentDedup", "MainWindow")
        self._last_result: DeduplicationResult | None = None

        # Debounce timer for search
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._apply_search_filter)

        self._build_ui()
        self._build_menu()
        self._connect_signals()
        self._theme.apply(self, "dark")
        self._restore_geometry()

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.setCentralWidget(splitter)

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_centre_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([280, 860, 340])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        self._splitter = splitter

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready — select a folder and click Scan.")

        # Tray icon
        self._tray = QSystemTrayIcon(QIcon.fromTheme("system-search"), self)
        self._tray.setVisible(True)

    # ---- LEFT PANEL ----
    def _build_left_panel(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Folder selector
        self._btn_folder = QPushButton("📁  Select Folder")
        self._btn_folder.setShortcut("Ctrl+O")
        self._lbl_folder = QLabel("No folder selected")
        self._lbl_folder.setWordWrap(True)
        self._lbl_folder.setAcceptDrops(True)
        self._lbl_folder.dragEnterEvent = self._drag_enter
        self._lbl_folder.dropEvent = self._drop_event

        # Min size filter
        self._spin_min_size = QSpinBox()
        self._spin_min_size.setRange(0, 500_000)
        self._spin_min_size.setValue(1)
        self._spin_min_size.setSuffix(" KB min size")

        # Max groups
        self._spin_max_groups = QSpinBox()
        self._spin_max_groups.setRange(0, 50_000)
        self._spin_max_groups.setValue(2000)
        self._spin_max_groups.setSuffix(" max groups (0=all)")

        # Algorithm selector
        self._combo_algo = QComboBox()
        self._combo_algo.addItems(["SHA-256 (Deep, Exact)", "MD5 (Fast, Exact)", "Simple (Name+Size)"])

        # Advanced options
        self._chk_semantic = self._make_checkbox("🧠  Semantic ML Matching")
        self._chk_fuzzy = self._make_checkbox("🔤  Fuzzy Name Matching")
        self._chk_agent = self._make_checkbox("🤖  AI Retention Agent", checked=True)

        # File type tree
        self._filter_tree = QTreeWidget()
        self._filter_tree.setHeaderLabel("File Types")
        self._populate_filter_tree()

        # Scan controls
        self._btn_scan = QPushButton("▶  Scan Now")
        self._btn_scan.setShortcut("Ctrl+Return")
        self._btn_pause = QPushButton("⏸  Pause")
        self._btn_pause.setEnabled(False)
        self._btn_cancel = QPushButton("⏹  Cancel")
        self._btn_cancel.setEnabled(False)

        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(self._btn_pause)
        ctrl_row.addWidget(self._btn_cancel)

        layout.addWidget(self._btn_folder)
        layout.addWidget(self._lbl_folder)
        layout.addWidget(self._spin_min_size)
        layout.addWidget(self._spin_max_groups)
        layout.addWidget(self._combo_algo)
        layout.addWidget(QLabel("Advanced:"))
        layout.addWidget(self._chk_semantic)
        layout.addWidget(self._chk_fuzzy)
        layout.addWidget(self._chk_agent)
        layout.addWidget(self._filter_tree)
        layout.addWidget(self._btn_scan)
        layout.addLayout(ctrl_row)

        return pane

    # ---- CENTRE PANEL ----
    def _build_centre_panel(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setTextVisible(True)

        # Live metrics label
        self._lbl_metrics = QLabel("Pass 0/3 | Files: 0 | Dupes: 0")
        self._lbl_metrics.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Search bar
        search_row = QHBoxLayout()
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("🔍 Filter by filename or path (regex supported)…")
        self._search_box.textChanged.connect(lambda _: self._search_timer.start())
        search_row.addWidget(self._search_box)

        # Action bar
        action_row = QHBoxLayout()
        self._combo_profile = QComboBox()
        self._combo_profile.addItems(["— Select Profile —", "Keep Oldest", "Keep Newest", "Keep Shortest Name", "AI Recommended"])
        self._combo_profile.currentIndexChanged.connect(self._apply_profile)

        self._btn_export = QPushButton("📄 Export CSV")
        self._btn_export.setShortcut("Ctrl+S")
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self._export_csv)

        self._lbl_selected = QLabel("Selected: 0 files from 0 groups")
        action_row.addWidget(self._combo_profile)
        action_row.addStretch()
        action_row.addWidget(self._lbl_selected)
        action_row.addWidget(self._btn_export)

        # Results table
        self._table = QTableView()
        self._table.setModel(self._results_model)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(False)
        self._table.setSortingEnabled(False)
        self._table.selectionModel().selectionChanged.connect(self._on_table_selection)

        # Delete bar
        delete_row = QHBoxLayout()
        self._combo_delete_method = QComboBox()
        self._combo_delete_method.addItems(["♻️  Recycle Bin (Safe)", "💀  Permanent Delete"])
        self._btn_delete = QPushButton("🗑  Delete Checked")
        self._btn_delete.setShortcut("Ctrl+D")
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._delete_checked)
        delete_row.addStretch()
        delete_row.addWidget(self._combo_delete_method)
        delete_row.addWidget(self._btn_delete)

        layout.addWidget(self._progress)
        layout.addWidget(self._lbl_metrics)
        layout.addLayout(search_row)
        layout.addLayout(action_row)
        layout.addWidget(self._table)
        layout.addLayout(delete_row)

        return pane

    # ---- RIGHT PANEL (AI Agent) ----
    def _build_right_panel(self) -> QWidget:
        from PyQt6.QtWidgets import QTextEdit
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(8, 8, 8, 8)

        lbl = QLabel("<b>🤖 AI Agent Recommendations</b>")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._agent_text = QTextEdit()
        self._agent_text.setReadOnly(True)
        self._agent_text.setPlaceholderText(
            "Run a scan with 'AI Retention Agent' enabled to see\n"
            "per-group file retention recommendations here."
        )

        self._btn_export_log = QPushButton("💾 Export Agent Log")
        self._btn_export_log.setEnabled(False)
        self._btn_export_log.clicked.connect(self._export_agent_log)

        layout.addWidget(lbl)
        layout.addWidget(self._agent_text, stretch=1)
        layout.addWidget(self._btn_export_log)
        return pane

    # ==================================================================
    # Menu Bar
    # ==================================================================

    def _build_menu(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("File")
        file_menu.addAction(self._action("Export CSV", self._export_csv, "Ctrl+S"))
        file_menu.addSeparator()
        file_menu.addAction(self._action("Exit", self.close))

        view_menu = mb.addMenu("View")
        view_menu.addAction(self._action("Toggle Left Panel", lambda: self._toggle_panel(0)))
        view_menu.addAction(self._action("Toggle Agent Panel", lambda: self._toggle_panel(2)))
        view_menu.addSeparator()
        view_menu.addAction(self._action("Lifetime Statistics", self._show_stats))

        theme_menu = mb.addMenu("Theme")
        for t in ("dark", "light", "grey"):
            theme_menu.addAction(self._action(t.capitalize(), lambda ch=False, th=t: self._theme.apply(self, th)))
        theme_menu.addSeparator()
        theme_menu.addAction(self._action("Cycle Theme", lambda: self._theme.cycle(self)))

    def _action(self, label: str, slot, shortcut: str = "") -> QAction:
        a = QAction(label, self)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(shortcut)
        return a

    # ==================================================================
    # Signal connections
    # ==================================================================

    def _connect_signals(self) -> None:
        self._btn_folder.clicked.connect(self._select_folder)
        self._btn_scan.clicked.connect(self._start_scan)
        self._btn_pause.clicked.connect(self._scan_vm.toggle_pause)
        self._btn_cancel.clicked.connect(self._scan_vm.cancel_scan)

        self._scan_vm.status_changed.connect(self._status.showMessage)
        self._scan_vm.progress_changed.connect(self._on_progress)
        self._scan_vm.scan_finished.connect(self._on_scan_finished)
        self._scan_vm.scan_error.connect(self._on_scan_error)
        self._scan_vm.is_scanning_changed.connect(self._on_scanning_state)

        self._results_model.selection_changed.connect(
            lambda files, groups: self._lbl_selected.setText(f"Selected: {files} files from {groups} groups")
        )

    # ==================================================================
    # Slots
    # ==================================================================

    def _select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Directory")
        if folder:
            self._lbl_folder.setText(folder)

    def _start_scan(self) -> None:
        folder = self._lbl_folder.text()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "Invalid Folder", "Please select a valid directory.")
            return

        algo_map = {0: "sha256", 1: "md5", 2: "simple"}
        algo = algo_map.get(self._combo_algo.currentIndex(), "sha256")
        exts = self._get_selected_extensions()
        if not exts:
            QMessageBox.warning(self, "No File Types", "Select at least one file type.")
            return

        self._results_model.beginResetModel()
        self._results_model.endResetModel()

        self._scan_vm.start_scan(
            folder=folder,
            allowed_extensions=exts,
            min_size_kb=self._spin_min_size.value(),
            algorithm=algo,
            use_semantic=self._chk_semantic.isChecked(),
            use_fuzzy=self._chk_fuzzy.isChecked(),
        )

    @pyqtSlot(int, int, int, int, str)
    def _on_progress(self, pass_num: int, done: int, total: int,
                     dupes: int, eta: str) -> None:
        self._lbl_metrics.setText(
            f"Pass {pass_num}/3 | Files: {done:,}/{total:,} | Dupes: {dupes:,} | ETA: {eta or '—'}"
        )
        if total > 0:
            self._progress.setRange(0, total)
            self._progress.setValue(done)
        else:
            self._progress.setRange(0, 0)

    @pyqtSlot(object)
    def _on_scan_finished(self, result: DeduplicationResult) -> None:
        self._last_result = result
        decisions = {}

        # Run AI agent if enabled
        if self._chk_agent.isChecked() and result.groups:
            try:
                from app.agents.reasoning_engine import ReasoningEngine
                engine = ReasoningEngine()
                decisions = engine.process(result.groups)
                self._agent_engine = engine
                self._render_agent_panel(decisions)
                self._btn_export_log.setEnabled(True)
            except Exception as exc:
                logger.error("Agent processing failed: %s", exc)

        self._results_model.load_result(
            result,
            decisions=decisions,
            max_groups=self._spin_max_groups.value(),
        )
        self._btn_delete.setEnabled(True)
        self._btn_export.setEnabled(True)

        self._tray.showMessage(
            "Scan Complete",
            f"Found {result.duplicate_groups} groups, {result.duplicate_files} files, "
            f"{result.space_recoverable_bytes / (1024**3):.2f} GB recoverable.",
            QSystemTrayIcon.MessageIcon.Information, 4000,
        )

    @pyqtSlot(str)
    def _on_scan_error(self, msg: str) -> None:
        QMessageBox.critical(self, "Scan Error", f"An error occurred:\n\n{msg}")

    @pyqtSlot(bool)
    def _on_scanning_state(self, scanning: bool) -> None:
        self._btn_scan.setEnabled(not scanning)
        self._btn_pause.setEnabled(scanning)
        self._btn_cancel.setEnabled(scanning)
        self._filter_tree.setEnabled(not scanning)
        self._progress.setVisible(scanning)

    def _on_table_selection(self) -> None:
        pass  # Preview panel hook (future)

    def _render_agent_panel(self, decisions: dict) -> None:
        lines = ["<h3>AI Retention Recommendations</h3>"]
        for key, decision in list(decisions.items())[:50]:
            conf_pct = int(decision.confidence * 100)
            colour = "#4caf50" if conf_pct >= 80 else "#ff9800" if conf_pct >= 50 else "#f44336"
            lines.append(
                f"<p><b>Group {key}:</b> Confidence <span style='color:{colour};'>{conf_pct}%</span><br>"
                f"<small>✅ Keep: <code>{decision.recommended_keep}</code></small></p>"
            )
            for flag in decision.scores[0].flags[:3]:
                lines.append(f"<small>&nbsp;&nbsp;{flag}</small><br>")
        self._agent_text.setHtml("".join(lines))

    # ==================================================================
    # File deletion
    # ==================================================================

    def _delete_checked(self) -> None:
        paths = self._results_model.get_checked_paths()
        if not paths:
            QMessageBox.information(self, "Nothing Checked", "Check files in the results table first.")
            return
        safe = self._combo_delete_method.currentIndex() == 0
        action_label = "move to Recycle Bin" if safe else "PERMANENTLY DELETE"
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to {action_label} {len(paths)} files?"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        failed: list[tuple[str, str]] = []
        for path in paths:
            try:
                if safe:
                    import send2trash
                    send2trash.send2trash(path)
                else:
                    os.remove(path)
                deleted += 1
            except PermissionError as exc:
                failed.append((path, f"Permission denied: {exc}"))
            except OSError as exc:
                failed.append((path, str(exc)))

        if failed:
            details = "\n".join(f"• {p}: {e}" for p, e in failed[:10])
            QMessageBox.warning(self, "Partial Failure",
                                f"Deleted {deleted} files. {len(failed)} failed:\n\n{details}")
        else:
            QMessageBox.information(self, "Done", f"Successfully deleted {deleted} files.")
        self._status.showMessage(f"Deleted {deleted} files.", 5000)

    # ==================================================================
    # Helpers
    # ==================================================================

    def _apply_search_filter(self) -> None:
        from PyQt6.QtCore import QSortFilterProxyModel
        # Simple text-based filter via proxy (future enhancement)
        pass

    def _apply_profile(self) -> None:
        pass  # Selection profiles (future)

    def _export_csv(self) -> None:
        import csv
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Group", "Filename", "Path", "Size (MB)", "Match Type", "Status"])
                model = self._results_model
                for r in range(model.rowCount()):
                    row_data = model._rows[r]
                    if not row_data.is_group_header:
                        writer.writerow([row_data.group_key, row_data.filename,
                                         row_data.path, row_data.size_mb,
                                         row_data.match_type, row_data.status])
            self._status.showMessage(f"Exported: {path}", 5000)
        except OSError as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))

    def _export_agent_log(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Agent Log", "agent_log.json", "JSON Files (*.json)")
        if path and hasattr(self, "_agent_engine"):
            self._agent_engine.export_log(path)
            self._status.showMessage(f"Agent log saved: {path}", 5000)

    def _show_stats(self) -> None:
        try:
            from app.models.database import init_db
            from app.models.repository import ScanRepository
            SessionLocal = init_db()
            with SessionLocal() as sess:
                repo = ScanRepository(sess)
                stats = repo.get_lifetime_stats()
            from app.views.dialogs.stats_dialog import StatsDialog
            StatsDialog(self, stats).exec()
        except Exception as exc:
            QMessageBox.information(self, "Statistics", f"Could not load stats: {exc}")

    def _toggle_panel(self, index: int) -> None:
        w = self._splitter.widget(index)
        if w:
            w.setVisible(not w.isVisible())

    def _populate_filter_tree(self) -> None:
        self._filter_tree.blockSignals(True)
        for cat, exts in FILE_CATEGORIES.items():
            parent = QTreeWidgetItem(self._filter_tree, [cat])
            parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            parent.setCheckState(0, Qt.CheckState.Checked)
            for ext in exts:
                child = QTreeWidgetItem(parent, [ext])
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Checked)
        self._filter_tree.blockSignals(False)
        self._filter_tree.collapseAll()

    def _get_selected_extensions(self) -> set[str]:
        exts: set[str] = set()
        root = self._filter_tree.invisibleRootItem()
        for i in range(root.childCount()):
            cat = root.child(i)
            for j in range(cat.childCount()):
                ext_item = cat.child(j)
                if ext_item.checkState(0) == Qt.CheckState.Checked:
                    exts.add(ext_item.text(0))
        return exts

    @staticmethod
    def _make_checkbox(label: str, checked: bool = False):
        from PyQt6.QtWidgets import QCheckBox
        cb = QCheckBox(label)
        cb.setChecked(checked)
        return cb

    def _drag_enter(self, event):
        if event.mimeData().hasUrls():
            event.accept()

    def _drop_event(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.isdir(path):
                self._lbl_folder.setText(path)

    # ==================================================================
    # Window state persistence
    # ==================================================================

    def _restore_geometry(self) -> None:
        geo = self._settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)

    def closeEvent(self, event) -> None:
        self._settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)
