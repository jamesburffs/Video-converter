"""Runs ffmpeg as a QProcess and reports progress via Qt signals."""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from .external_env import clean_qprocess_environment


class ConversionRunner(QObject):
    progress = Signal(float)       # percent complete, 0-100
    log_line = Signal(str)         # a line of ffmpeg stderr output
    finished = Signal(bool, str)   # success, message
    started = Signal()

    def __init__(self, duration_s: float, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._duration_s = max(duration_s, 0.0)
        self._process: Optional[QProcess] = None
        self._stdout_buffer = ""
        self._cancelled = False

    def start(self, command: List[str]):
        self._cancelled = False
        self._process = QProcess(self)
        self._process.setProcessEnvironment(clean_qprocess_environment())
        self._process.setProgram(command[0])
        self._process.setArguments(command[1:])
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)
        self._process.start()
        self.started.emit()

    def cancel(self):
        # Deliberately non-blocking: terminate() is enough to make the
        # process exit, and its already-connected `finished` signal takes
        # care of the rest via the normal event loop. A blocking
        # waitForFinished() here is a reentrancy hazard - while it pumps
        # events waiting for the process to exit, Qt can dispatch that same
        # `finished` signal inline, which (via MainWindow) tears this very
        # ConversionRunner down while cancel() is still executing on it.
        if not self._process or self._process.state() == QProcess.NotRunning:
            return
        self._cancelled = True
        self._process.terminate()
        QTimer.singleShot(3000, self._kill_if_still_running)

    def _kill_if_still_running(self):
        if self._process and self._process.state() != QProcess.NotRunning:
            self._process.kill()

    def _on_stdout(self):
        if not self._process:
            return
        data = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        self._stdout_buffer += data
        while "\n" in self._stdout_buffer:
            line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
            self._handle_progress_line(line.strip())

    def _handle_progress_line(self, line: str):
        if not line or "=" not in line:
            return
        key, _, value = line.partition("=")
        if key == "out_time_us" or key == "out_time_ms":
            try:
                out_us = float(value)
                # ffmpeg's out_time_ms field is actually microseconds too
                # in modern builds; normalize by comparing to duration.
                seconds = out_us / 1_000_000.0
            except ValueError:
                return
            if self._duration_s > 0:
                pct = max(0.0, min(100.0, (seconds / self._duration_s) * 100.0))
                self.progress.emit(pct)
        elif key == "progress" and value == "end":
            self.progress.emit(100.0)

    def _on_stderr(self):
        if not self._process:
            return
        data = bytes(self._process.readAllStandardError()).decode(
            "utf-8", errors="replace"
        )
        for line in data.splitlines():
            if line.strip():
                self.log_line.emit(line.rstrip())

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        if self._cancelled:
            self.finished.emit(False, "Conversion cancelled.")
        elif exit_code == 0 and exit_status == QProcess.NormalExit:
            self.finished.emit(True, "Conversion completed successfully.")
        else:
            self.finished.emit(
                False, f"ffmpeg exited with code {exit_code}. See log for details."
            )

    def _on_error(self, error: QProcess.ProcessError):
        # QProcess also reports Crashed here when a running process is
        # terminated/killed (e.g. by cancel()) - that case is already
        # handled by _on_finished via the process's own `finished` signal,
        # so only FailedToStart (the binary couldn't be launched at all,
        # which never fires `finished`) is handled here. Using process
        # state instead of the error code to distinguish the two would
        # double-emit our `finished` signal for a plain cancellation,
        # surfacing a bogus "Conversion failed" popup.
        if error == QProcess.ProcessError.FailedToStart:
            self.finished.emit(False, f"Failed to start ffmpeg: {error}")
