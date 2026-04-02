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
import json
from pathlib import Path

from PyQt6.QtCore import Qt, QSettings, QTimer, pyqtSlot
from PyQt6.QtGui import QAction, QIcon, QPixmap
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
        self._current_session_id: int | None = None

        # Debounce timer for search
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._apply_search_filter)

        self._build_ui()
        self._build_menu()
        self._connect_signals()
        self._restore_settings()
        self._restore_geometry()
        QTimer.singleShot(100, self._load_latest_session)

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
        
        self._lbl_status_stats = QLabel("Lifetime Deleted: 0 files | Freed: 0.00 MB")
        self._lbl_status_stats.setStyleSheet("padding: 0 10px;")
        self._status.addPermanentWidget(self._lbl_status_stats)
        self._update_status_stats()

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

        self._btn_summary = QPushButton("📊 View Run Summary")
        self._btn_summary.setEnabled(False)
        self._btn_summary.clicked.connect(self._show_run_summary)

        self._lbl_selected = QLabel("Selected: 0 files from 0 groups (0.00 MB recoverable)")
        action_row.addWidget(self._combo_profile)
        action_row.addStretch()
        action_row.addWidget(self._lbl_selected)
        action_row.addWidget(self._btn_summary)
        action_row.addWidget(self._btn_export)

        # Results table
        self._table = QTableView()
        self._table.setModel(self._results_model)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(False)
        self._table.setSortingEnabled(False)
        self._table.selectionModel().selectionChanged.connect(self._on_table_selection)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_table_context_menu)

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
        from PyQt6.QtWidgets import QTextEdit, QSplitter
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(8, 8, 8, 8)

        self._right_splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. Preview Image
        img_container = QWidget()
        img_layout = QVBoxLayout(img_container)
        img_layout.setContentsMargins(0, 0, 0, 0)
        lbl_img = QLabel("<b>👁️ Selection Preview</b>")
        lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_image = QLabel()
        self._preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_layout.addWidget(lbl_img)
        img_layout.addWidget(self._preview_image, stretch=1)
        
        # 2. Preview Text
        txt_container = QWidget()
        txt_layout = QVBoxLayout(txt_container)
        txt_layout.setContentsMargins(0, 0, 0, 0)
        lbl_txt = QLabel("<b>📄 File Description</b>")
        lbl_txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_text = QTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setPlaceholderText("Select a file in the table to view its properties.")
        txt_layout.addWidget(lbl_txt)
        txt_layout.addWidget(self._preview_text, stretch=1)

        # 3. AI Agent
        ai_container = QWidget()
        ai_layout = QVBoxLayout(ai_container)
        ai_layout.setContentsMargins(0, 0, 0, 0)
        lbl_ai = QLabel("<b>🤖 AI Agent Recommendations</b>")
        lbl_ai.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._agent_text = QTextEdit()
        self._agent_text.setReadOnly(True)
        self._agent_text.setPlaceholderText(
            "Run a scan with 'AI Retention Agent' enabled to see\n"
            "per-group file retention recommendations here."
        )
        ai_layout.addWidget(lbl_ai)
        ai_layout.addWidget(self._agent_text, stretch=1)

        self._right_splitter.addWidget(img_container)
        self._right_splitter.addWidget(txt_container)
        self._right_splitter.addWidget(ai_container)
        self._right_splitter.setSizes([200, 150, 400])

        layout.addWidget(self._right_splitter)
        return pane

    # ==================================================================
    # Menu Bar
    # ==================================================================

    def _build_menu(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("File")
        file_menu.addAction(self._action("Load Previous Session", self._load_session, "Ctrl+L"))
        file_menu.addSeparator()
        file_menu.addAction(self._action("Export CSV", self._export_csv, "Ctrl+S"))
        self._action_export_log = self._action("Export Agent Log", self._export_agent_log)
        self._action_export_log.setEnabled(False)
        file_menu.addAction(self._action_export_log)
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

        help_menu = mb.addMenu("Help")
        help_menu.addAction(self._action("Changelog", self._show_changelog))
        help_menu.addAction(self._action("Features List", self._show_features))

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

        self._results_model.selection_changed.connect(self._update_selection_metrics)

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

        self._persist_current_session_state()

        self._agent_text.clear()
        self._preview_text.clear()
        self._preview_image.clear()
        self._lbl_selected.setText("Selected: 0 files from 0 groups (0.00 MB recoverable)")
        self._btn_summary.setEnabled(False)
        self._btn_export.setEnabled(False)
        self._btn_delete.setEnabled(False)
        if hasattr(self, '_action_export_log'):
            self._action_export_log.setEnabled(False)

        self._results_model.beginResetModel()
        self._results_model._rows.clear()
        self._results_model.endResetModel()
        
        self._update_status_stats()

        import time
        self._scan_start_time = time.monotonic()

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
        import time
        elapsed = time.monotonic() - getattr(self, "_scan_start_time", time.monotonic())
        m, s = divmod(int(elapsed), 60)
        h, m = divmod(m, 60)
        elapsed_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

        self._lbl_metrics.setText(
            f"Pass {pass_num}/3 | Files: {done:,}/{total:,} | Dupes: {dupes:,} | Elapsed: {elapsed_str} | ETA: {eta or '—'}"
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

        try:
            from app.models.database import init_db
            from app.models.repository import ScanRepository
            SessionLocal = init_db()
            with SessionLocal() as sess:
                repo = ScanRepository(sess)
                db_sess = repo.create_session(
                    folder_path=self._lbl_folder.text(),
                    comparison_method=self._combo_algo.currentText(),
                    used_semantic=self._chk_semantic.isChecked(),
                    used_fuzzy=self._chk_fuzzy.isChecked(),
                    used_phash=False
                )
                for g in result.groups:
                    repo.create_group(
                        session_id=db_sess.id,
                        group_key=g.group_key,
                        match_type=g.match_type,
                        file_paths=g.file_paths,
                        space_recoverable_bytes=g.space_recoverable_bytes
                    )
                repo.complete_session(
                    session_id=db_sess.id,
                    files_scanned=result.files_scanned,
                    duplicate_groups=result.duplicate_groups,
                    duplicate_files=result.duplicate_files,
                    space_recoverable_bytes=result.space_recoverable_bytes
                )
                self._current_session_id = db_sess.id
        except Exception as exc:
            logger.error("Failed to save scan session: %s", exc)

        # Run AI agent if enabled
        if self._chk_agent.isChecked() and result.groups:
            try:
                from app.agents.reasoning_engine import ReasoningEngine
                engine = ReasoningEngine()
                decisions = engine.process(result.groups)
                self._agent_engine = engine
                self._render_agent_panel(decisions)
                if hasattr(self, '_action_export_log'):
                    self._action_export_log.setEnabled(True)
                    
                # Save agent decisions to Database for continuous persistence
                from app.models.database import init_db
                from app.models.repository import ScanRepository
                SessionLocal = init_db()
                with SessionLocal() as sess:
                    repo = ScanRepository(sess)
                    db_groups = repo.get_groups_for_session(self._current_session_id)
                    for db_g in db_groups:
                        decision = decisions.get(db_g.group_key)
                        if decision:
                            repo.update_group_agent_decision(
                                group_id=db_g.id,
                                recommended_keep=decision.recommended_keep,
                                confidence=decision.confidence,
                                reasoning=[]
                            )
            except Exception as exc:
                logger.error("Agent processing failed: %s", exc)

        self._results_model.load_result(
            result,
            decisions=decisions,
            max_groups=self._spin_max_groups.value(),
        )
        self._btn_delete.setEnabled(True)
        self._btn_export.setEnabled(True)
        self._btn_summary.setEnabled(True)

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
        idx = self._table.currentIndex()
        if not idx.isValid():
            self._preview_text.clear()
            self._preview_image.clear()
            return
            
        row = idx.row()
        if row < 0 or row >= len(self._results_model._rows):
            return
            
        row_data = self._results_model._rows[row]
        
        if row_data.is_group_header:
            self._preview_text.setHtml(f"<h3>Group Header</h3><p>{row_data.path}</p>")
            self._preview_image.clear()
            return
            
        if row_data.status.lower() == "deleted" or not os.path.exists(row_data.path):
            self._preview_text.setHtml(f"<h2><font color='red'>FILE DELETED</font></h2><p><b>Path:</b> <del>{row_data.path}</del><br>This file is no longer present on the disk.</p>")
            self._preview_image.clear()
            self._results_model.mark_deleted(row)
            self._persist_current_session_state()
            self._update_status_stats()
            return
            
        html = f"<h3>{row_data.filename}</h3>"
        html += f"<p><b>Path:</b> {row_data.path}<br>"
        html += f"<b>Size:</b> {row_data.size_mb} MB<br>"
        html += f"<b>Modified:</b> {row_data.modified_str}<br>"
        html += f"<b>Status:</b> {row_data.status}</p>"
        self._preview_text.setHtml(html)
        
        ext = os.path.splitext(row_data.filename)[1].lower()
        if ext in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}:
            pixmap = QPixmap(row_data.path)
            if not pixmap.isNull():
                self._preview_image.setPixmap(pixmap.scaled(
                    300, 300, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                ))
            else:
                self._preview_image.setText("<i>Preview unable to load</i>")
        else:
            self._preview_image.clear()

    def _on_table_context_menu(self, pos) -> None:
        idx = self._table.indexAt(pos)
        if not idx.isValid():
            return
            
        row = idx.row()
        if row < 0 or row >= len(self._results_model._rows):
            return
            
        row_data = self._results_model._rows[row]
        if row_data.is_group_header or row_data.status.lower() == "deleted":
            return
            
        if not os.path.exists(row_data.path):
            return
            
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction
        import subprocess
        
        menu = QMenu(self)
        
        action_open_file = QAction("🗔 Open File", self)
        def open_file():
            try:
                if os.name == 'nt':
                    os.startfile(row_data.path)
                else:
                    import sys
                    opener = "open" if sys.platform == "darwin" else "xdg-open"
                    subprocess.call([opener, row_data.path])
            except Exception as e:
                import logging
                logging.error(f"Failed to open file: {e}")
        action_open_file.triggered.connect(open_file)
        menu.addAction(action_open_file)
        
        action_open_loc = QAction("📂 Open File Location", self)
        def open_location():
            if os.name == 'nt':
                subprocess.Popen(f'explorer /select,"{os.path.normpath(row_data.path)}"')
            else:
                import sys
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.call([opener, os.path.dirname(row_data.path)])

        action_open_loc.triggered.connect(open_location)
        menu.addAction(action_open_loc)
        
        menu.exec(self._table.viewport().mapToGlobal(pos))

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
        items = self._results_model.get_checked_items()
        if not items:
            QMessageBox.information(self, "Nothing Checked", "Check files in the results table first.")
            return
            
        safe = self._combo_delete_method.currentIndex() == 0
        action_label = "move to Recycle Bin" if safe else "PERMANENTLY DELETE"
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to {action_label} {len(items)} files?"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        freed_bytes = 0
        failed: list[tuple[str, str]] = []
        
        try:
            from app.models.database import init_db
            from app.models.repository import ScanRepository
            SessionLocal = init_db()
            db_sess = SessionLocal()
            repo = ScanRepository(db_sess)
        except Exception as exc:
            QMessageBox.critical(self, "DB Error", f"Cannot open database context: {exc}")
            return

        try:
            for row_idx, path in items:
                size = 0
                if os.path.exists(path):
                    size = os.path.getsize(path)
                else:
                    # File is already missing; treat as success
                    self._results_model.mark_deleted(row_idx)
                    deleted += 1
                    continue
                    
                try:
                    if safe:
                        import send2trash
                        send2trash.send2trash(path)
                    else:
                        os.remove(path)
                    self._results_model.mark_deleted(row_idx)
                    repo.log_action(full_path=path, action="deleted", freed_bytes=size)
                    deleted += 1
                    freed_bytes += size
                except Exception as exc:
                    failed.append((path, str(exc)))
        finally:
            db_sess.close()

        if failed:
            details = "\n".join(f"• {p}: {e}" for p, e in failed[:10])
            QMessageBox.warning(self, "Partial Failure",
                                f"Deleted {deleted} files. {len(failed)} failed:\n\n{details}")
        
        freed_mb = freed_bytes / (1024 * 1024)
        self._status.showMessage(f"Deleted {deleted} files and freed {freed_mb:.2f} MB space.", 5000)
        self._table.clearSelection()
        self._update_status_stats()
        self._persist_current_session_state()

    # ==================================================================
    # Helpers
    # ==================================================================

    def _update_status_stats(self) -> None:
        if not hasattr(self, '_lbl_status_stats'):
            return
            
        try:
            from app.models.database import init_db
            from app.models.repository import ScanRepository
            SessionLocal = init_db()
            with SessionLocal() as sess:
                repo = ScanRepository(sess)
                stats = repo.get_lifetime_stats()
                
            deleted = stats.get("total_files_deleted", 0)
            freed_bytes = stats.get("total_space_freed_bytes", 0)
            freed_mb = freed_bytes / (1024 * 1024)
            self._lbl_status_stats.setText(f"Lifetime Deleted: {deleted:,} files | Freed: {freed_mb:,.2f} MB")
        except Exception as exc:
            import logging
            logging.error(f"Could not load lifetime stats for status bar: {exc}")

    def _update_selection_metrics(self, files: int, groups: int, size: int) -> None:
        self._lbl_selected.setText(
            f"Selected: {files} files from {groups} groups ({size / (1024*1024):.2f} MB recoverable)"
        )
        self._btn_delete.setEnabled(files > 0)

    def _apply_search_filter(self) -> None:
        """Placeholder for future regex/search filtering."""
        pass


    def _show_run_summary(self) -> None:
        if not self._last_result:
            return
            
        run_date = "Unknown"
        folder_scanned = self._lbl_folder.text()
        if getattr(self, "_current_session_id", None):
            try:
                from app.models.database import init_db
                from app.models.repository import ScanRepository
                SessionLocal = init_db()
                with SessionLocal() as sess:
                    repo = ScanRepository(sess)
                    db_sess = repo.get_session(self._current_session_id)
                    if db_sess:
                        run_date = db_sess.started_at_human()
                        folder_scanned = db_sess.folder_path
            except Exception as exc:
                logging.error("Could not fetch session info: %s", exc)

        r = self._last_result
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton
        dialog = QDialog(self)
        dialog.setWindowTitle("Run Summary")
        dialog.resize(600, 350)
        
        layout = QVBoxLayout(dialog)
        table = QTableWidget(7, 2)
        table.setHorizontalHeaderLabels(["Metric", "Value"])
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        items = [
            ("Run Date & Time", run_date),
            ("Folder Scanned", folder_scanned),
            ("Files Scanned", f"{r.files_scanned:,}"),
            ("Duplicate Files", f"{r.duplicate_files:,}"),
            ("Duplicate Groups", f"{r.duplicate_groups:,}"),
            ("Space Recoverable", f"{r.space_recoverable_bytes / (1024*1024):.2f} MB"),
            ("Duration", f"{r.duration_seconds:.1f} s")
        ]
        
        for i, (metric, val) in enumerate(items):
            table.setItem(i, 0, QTableWidgetItem(metric))
            table.setItem(i, 1, QTableWidgetItem(val))
            
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.setColumnWidth(0, 150)
        table.setColumnWidth(1, 400)
        layout.addWidget(table)
        
        btn_row = QHBoxLayout()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dialog.accept)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)
        
        dialog.exec()

    def _show_changelog(self) -> None:
        import os
        from PyQt6.QtWidgets import QDialog, QTextEdit, QVBoxLayout
        changelog_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "CHANGELOG.md")
        if not os.path.exists(changelog_path):
            QMessageBox.information(self, "Changelog", "Changelog file not found.")
            return
            
        with open(changelog_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Change Log")
        dialog.resize(600, 400)
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setMarkdown(content)
        layout.addWidget(text_edit)
        dialog.exec()

    def _show_features(self) -> None:
        import os
        from PyQt6.QtWidgets import QDialog, QTextEdit, QVBoxLayout
        features_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "FEATURES.md")
        if not os.path.exists(features_path):
            QMessageBox.information(self, "Features List", "Features list file not found.")
            return
            
        with open(features_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Application Features")
        dialog.resize(600, 400)
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setMarkdown(content)
        layout.addWidget(text_edit)
        dialog.exec()

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

    def _load_latest_session(self) -> None:
        try:
            from app.models.database import init_db
            from app.models.repository import ScanRepository
            SessionLocal = init_db()
            with SessionLocal() as sess:
                repo = ScanRepository(sess)
                latest = repo.get_latest_session()
                if latest:
                    self._restore_session_from_db(repo, latest.id)
        except Exception as exc:
            logger.error("Failed to load latest session on startup: %s", exc)

    def _persist_current_session_state(self) -> None:
        if getattr(self, "_current_session_id", None) is None:
            return
        try:
            checked = self._results_model.get_checked_paths()
            deleted = [row.path for row in self._results_model._rows if row.status.lower() == "deleted"]
            from app.models.database import init_db
            from app.models.repository import ScanRepository
            SessionLocal = init_db()
            with SessionLocal() as sess:
                repo = ScanRepository(sess)
                repo.update_session_state(self._current_session_id, {
                    "checked": checked,
                    "deleted": deleted
                })
        except Exception as exc:
            logger.error("Failed to persist session state: %s", exc)

    def _load_session(self) -> None:
        try:
            from app.models.database import init_db
            from app.models.repository import ScanRepository
            from app.views.dialogs.load_session_dialog import LoadSessionDialog
            SessionLocal = init_db()
            with SessionLocal() as sess:
                repo = ScanRepository(sess)
                sessions = repo.list_sessions(limit=50)
                if not sessions:
                    QMessageBox.information(self, "No Sessions", "No previous scan sessions found.")
                    return
                dialog = LoadSessionDialog(self, sessions)
                if dialog.exec():
                    session_id = dialog.selected_session_id
                    if session_id:
                        self._restore_session_from_db(repo, session_id)
        except Exception as exc:
            QMessageBox.critical(self, "Error Loading Session", f"Failed to load session: {exc}")

    def _restore_session_from_db(self, repo, session_id: int) -> None:
        db_sess = repo.get_session(session_id)
        if not db_sess:
            return
            
        db_groups = repo.get_groups_for_session(session_id)
        
        from app.engine.deduplicator import DeduplicationResult, DuplicateGroup
        groups = [
            DuplicateGroup(
                group_key=g.group_key,
                match_type=g.match_type,
                file_paths=g.file_paths,
                space_recoverable_bytes=g.space_recoverable_bytes,
            )
            for g in db_groups
        ]
        
        result = DeduplicationResult(
            groups=groups,
            files_scanned=db_sess.files_scanned,
            duplicate_files=db_sess.duplicate_files,
            space_recoverable_bytes=db_sess.space_recoverable_bytes,
            duration_seconds=db_sess.duration_seconds or 0.0,
            passes_completed=3 if db_sess.used_semantic else 2
        )
        
        self._lbl_folder.setText(db_sess.folder_path)
        self._current_session_id = session_id
        self._last_result = result
        
        decisions = {}
        if db_sess.used_semantic or True:
            from app.agents.retention_agent import AgentDecision
            for g in db_groups:
                if getattr(g, "agent_recommended_keep", None):
                    decisions[g.group_key] = AgentDecision(
                        recommended_keep=g.agent_recommended_keep,
                        confidence=g.agent_confidence or 0.0,
                        scores=[],
                        reasoning=g.agent_reasoning_json or "",
                    )
        if not decisions and self._chk_agent.isChecked() and groups:
            try:
                from app.agents.reasoning_engine import ReasoningEngine
                engine = ReasoningEngine()
                decisions = engine.process(groups)
                self._agent_engine = engine
                self._render_agent_panel(decisions)
                if hasattr(self, '_action_export_log'):
                    self._action_export_log.setEnabled(True)
                
                for db_g in db_groups:
                    decision = decisions.get(db_g.group_key)
                    if decision:
                        repo.update_group_agent_decision(
                            group_id=db_g.id,
                            recommended_keep=decision.recommended_keep,
                            confidence=decision.confidence,
                            reasoning=[]
                        )
            except Exception as exc:
                import logging
                logging.error(f"Failed to regenerate agent processing on session load: {exc}")

        self._results_model.load_result(result, decisions=decisions, max_groups=self._spin_max_groups.value())
        
        if db_sess.user_state_json:
            try:
                state = json.loads(db_sess.user_state_json)
                checked_paths = set(state.get("checked", []))
                deleted_paths = set(state.get("deleted", []))
                
                self._results_model.layoutAboutToBeChanged.emit()
                for i, row in enumerate(self._results_model._rows):
                    if not row.is_group_header:
                        if row.path in checked_paths:
                            self._results_model._checked.add(i)
                        if row.path in deleted_paths:
                            row.status = "Deleted"
                self._results_model.layoutChanged.emit()
                self._results_model._emit_selection_changed()
            except Exception as exc:
                logger.error("Failed to restore session state: %s", exc)

        if decisions:
            self._render_agent_panel(decisions)
            if hasattr(self, '_action_export_log'):
                self._action_export_log.setEnabled(True)

        self._btn_delete.setEnabled(True)
        self._btn_export.setEnabled(True)
        self._btn_summary.setEnabled(True)
        self._update_status_stats()
        self._status.showMessage(f"Loaded session: {db_sess.started_at_human()}")

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
        self._filter_tree.itemChanged.connect(self._on_filter_tree_item_changed)
        self._filter_tree.blockSignals(False)
        self._filter_tree.collapseAll()

    def _on_filter_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        self._filter_tree.blockSignals(True)
        state = item.checkState(column)
        if item.parent() is None:
            for i in range(item.childCount()):
                item.child(i).setCheckState(column, state)
        self._filter_tree.blockSignals(False)

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

    def _restore_settings(self) -> None:
        folder = self._settings.value("folder", "")
        if folder and os.path.exists(folder):
            self._lbl_folder.setText(folder)
            
        if self._settings.contains("min_size"):
            self._spin_min_size.setValue(int(self._settings.value("min_size")))
        if self._settings.contains("max_groups"):
            self._spin_max_groups.setValue(int(self._settings.value("max_groups")))
        if self._settings.contains("algo_index"):
            self._combo_algo.setCurrentIndex(int(self._settings.value("algo_index")))
            
        self._chk_semantic.setChecked(self._settings.value("semantic", False, type=bool))
        self._chk_fuzzy.setChecked(self._settings.value("fuzzy", False, type=bool))
        self._chk_agent.setChecked(self._settings.value("agent", True, type=bool))
        
        theme = self._settings.value("theme", "dark", type=str)
        self._theme.apply(self, theme)

    def _restore_geometry(self) -> None:
        geo = self._settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
            
        windowState = self._settings.value("windowState")
        if windowState:
            self.restoreState(windowState)
            
        main_splitter = self._settings.value("main_splitter")
        if main_splitter and hasattr(self, "_splitter"):
            self._splitter.restoreState(main_splitter)
            
        right_splitter = self._settings.value("right_splitter")
        if right_splitter and hasattr(self, "_right_splitter"):
            self._right_splitter.restoreState(right_splitter)
            
        table_header = self._settings.value("table_header")
        if table_header and hasattr(self, "_table"):
            self._table.horizontalHeader().restoreState(table_header)

    def closeEvent(self, event) -> None:
        self._persist_current_session_state()
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("windowState", self.saveState())
        
        if hasattr(self, "_splitter"):
            self._settings.setValue("main_splitter", self._splitter.saveState())
        if hasattr(self, "_right_splitter"):
            self._settings.setValue("right_splitter", self._right_splitter.saveState())
        if hasattr(self, "_table"):
            self._settings.setValue("table_header", self._table.horizontalHeader().saveState())
        self._settings.setValue("folder", self._lbl_folder.text())
        self._settings.setValue("min_size", self._spin_min_size.value())
        self._settings.setValue("max_groups", self._spin_max_groups.value())
        self._settings.setValue("algo_index", self._combo_algo.currentIndex())
        self._settings.setValue("semantic", self._chk_semantic.isChecked())
        self._settings.setValue("fuzzy", self._chk_fuzzy.isChecked())
        self._settings.setValue("agent", self._chk_agent.isChecked())
        self._settings.setValue("theme", self._theme.current_theme)
        super().closeEvent(event)
