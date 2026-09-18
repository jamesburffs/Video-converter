"""Runs a batch-folder scan (finding video files, then ffprobing each one)
on a background thread.

batch.probe_one() shells out to ffprobe synchronously per file - scanning a
folder used to mean calling it in a loop on the UI thread, with only
QApplication.processEvents() between iterations to fake responsiveness.
That visibly freezes/stutters the window on a folder with many files. This
moves the whole scan off the UI thread via the standard Qt worker-object
pattern (a QObject moved to a QThread, driven by signals) instead.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from . import batch


class _BatchScanWorker(QObject):
    """Lives on its own QThread once started (see BatchScanner.start) - its
    methods run off the main/UI thread from that point on."""

    item_probed = Signal(object, int, int)  # BatchItem, index (1-based), total
    finished = Signal(list)  # list[BatchItem], in the order files were found

    def __init__(self, folder: str, recursive: bool):
        super().__init__()
        self._folder = folder
        self._recursive = recursive
        self._cancelled = False

    def cancel(self):
        # Cooperative only: doesn't interrupt a ffprobe subprocess call
        # already in flight (bounded by its own timeout in probe.py), just
        # stops the loop from starting another one.
        self._cancelled = True

    def run(self):
        paths = batch.find_video_files(self._folder, self._recursive)
        items = []
        total = len(paths)
        for idx, p in enumerate(paths, start=1):
            if self._cancelled:
                break
            item = batch.probe_one(p)
            items.append(item)
            self.item_probed.emit(item, idx, total)
        self.finished.emit(items)


class BatchScanner(QObject):
    """Owns (at most) one in-flight scan's worker thread. Starting a new
    scan while one is already running cancels and detaches the old one
    (its results are simply never wired up to anything, and it's left to
    finish and clean itself up in the background) rather than letting two
    scans race to update the UI."""

    item_probed = Signal(object, int, int)
    finished = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _BatchScanWorker | None = None

    def start(self, folder: str, recursive: bool):
        self._detach_current()

        thread = QThread()
        worker = _BatchScanWorker(folder, recursive)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.item_probed.connect(self.item_probed)
        worker.finished.connect(self.finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        # A scan that finishes on its own (the common case) must clear
        # these too - otherwise they're left pointing at a thread/worker
        # that deleteLater() has since torn down, and a later shutdown()
        # call (e.g. on window close, long after an unrelated scan quietly
        # finished) would touch an already-deleted QThread. Guarded by
        # identity in case a newer scan has since replaced this one via
        # _detach_current, which must not have its own state clobbered by a
        # stale signal from this older thread arriving after the fact.
        thread.finished.connect(lambda t=thread: self._clear_if_current(t))

        self._thread = thread
        self._worker = worker
        thread.start()

    def _clear_if_current(self, thread: QThread):
        if self._thread is thread:
            self._thread = None
            self._worker = None

    def shutdown(self, wait_ms: int = 5000):
        """Cancel and wait for any in-flight scan - call this before the
        owning window closes, so the process doesn't exit out from under a
        still-running background thread."""
        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(wait_ms)
        self._thread = None
        self._worker = None

    def _detach_current(self):
        if self._thread is None:
            return
        self._worker.cancel()
        try:
            self._worker.item_probed.disconnect(self.item_probed)
            self._worker.finished.disconnect(self.finished)
        except (TypeError, RuntimeError):
            pass
        self._thread = None
        self._worker = None
