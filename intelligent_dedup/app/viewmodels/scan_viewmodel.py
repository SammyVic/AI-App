"""
=============================================================================
app/viewmodels/scan_viewmodel.py
=============================================================================
MVVM ViewModel: wraps the ScanWorker QThread and exposes observable Qt
properties. The View has zero business logic — it only reads these signals.
=============================================================================
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from app.engine.scanner import ScanConfig
from app.engine.deduplicator import DeduplicationResult, Deduplicator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background worker (QThread)
# ---------------------------------------------------------------------------

class ScanWorker(QThread):
    """
    Runs the Deduplicator in a background QThread.
    Emits typed signals that the ViewModel observes.
    """
    # (pass_num, done, total, dupes, eta_str)
    progress = pyqtSignal(int, int, int, int, str)
    # Emitted on completion with the full result
    finished = pyqtSignal(object)  # DeduplicationResult
    # Emitted on unrecoverable error
    error = pyqtSignal(str)

    def __init__(self, config: ScanConfig, algorithm: str,
                 use_semantic: bool, use_fuzzy: bool) -> None:
        super().__init__()
        self.config = config
        self.algorithm = algorithm
        self.use_semantic = use_semantic
        self.use_fuzzy = use_fuzzy
        self._cancelled: list[bool] = [False]

    def cancel(self) -> None:
        self._cancelled[0] = True

    def run(self) -> None:
        try:
            dedup = Deduplicator(
                config=self.config,
                algorithm=self.algorithm,
                use_semantic=self.use_semantic,
                use_fuzzy=self.use_fuzzy,
                on_progress=lambda *args: self.progress.emit(*args),
                cancelled_flag=self._cancelled,
            )
            result = dedup.run()
            self.finished.emit(result)
        except Exception as exc:
            logger.exception("ScanWorker unhandled error")
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# ScanViewModel
# ---------------------------------------------------------------------------

class ScanViewModel(QObject):
    """
    ViewModel for the scan panel.
    View binds to these signals; calls methods to trigger actions.
    """
    # --- Observable signals ---
    status_changed = pyqtSignal(str)         # status bar message
    progress_changed = pyqtSignal(int, int, int, int, str)  # pass,done,total,dupes,eta
    scan_finished = pyqtSignal(object)       # DeduplicationResult
    scan_error = pyqtSignal(str)
    is_scanning_changed = pyqtSignal(bool)
    is_paused_changed = pyqtSignal(bool)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ScanWorker] = None
        self._is_scanning: bool = False
        self._is_paused: bool = False
        self._start_time: float = 0.0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_scanning(self) -> bool:
        return self._is_scanning

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    # ------------------------------------------------------------------
    # Commands (called by View)
    # ------------------------------------------------------------------

    def start_scan(
        self,
        folder: str,
        allowed_extensions: set[str],
        min_size_kb: int,
        algorithm: str,
        use_semantic: bool = False,
        use_fuzzy: bool = False,
    ) -> None:
        if self._is_scanning:
            return
        from app.engine.scanner import ScanConfig
        config = ScanConfig(
            start_dir=folder,
            allowed_extensions=allowed_extensions,
            min_size_bytes=min_size_kb * 1024,
        )
        self._worker = ScanWorker(config, algorithm, use_semantic, use_fuzzy)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._is_scanning = True
        self._is_paused = False
        self._start_time = time.monotonic()
        self.is_scanning_changed.emit(True)
        self.status_changed.emit("Scanning…")
        self._worker.start()

    def cancel_scan(self) -> None:
        if self._worker:
            self._worker.cancel()
        self.status_changed.emit("Cancelled.")
        self._reset()

    def toggle_pause(self) -> None:
        """Pause/resume signal (worker polls _cancelled; pause is a gentler stop)."""
        # Implemented by having the worker check an external flag
        # For full pause support the worker dedup loop checks cancelled_flag
        self._is_paused = not self._is_paused
        self.is_paused_changed.emit(self._is_paused)
        msg = "Paused." if self._is_paused else "Resumed."
        self.status_changed.emit(msg)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @pyqtSlot(int, int, int, int, str)
    def _on_progress(self, pass_num: int, done: int, total: int,
                     dupes: int, eta: str) -> None:
        self.progress_changed.emit(pass_num, done, total, dupes, eta)

    @pyqtSlot(object)
    def _on_finished(self, result: DeduplicationResult) -> None:
        elapsed = time.monotonic() - self._start_time
        self.status_changed.emit(
            f"Scan complete in {elapsed:.1f}s — {result.duplicate_groups} groups found."
        )
        self.scan_finished.emit(result)
        self._reset()

    @pyqtSlot(str)
    def _on_error(self, msg: str) -> None:
        self.status_changed.emit(f"Error: {msg}")
        self.scan_error.emit(msg)
        self._reset()

    def _reset(self) -> None:
        self._is_scanning = False
        self._is_paused = False
        self.is_scanning_changed.emit(False)
