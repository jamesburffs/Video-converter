"""Modal dialog shown while a conversion (single-file or batch) is running."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QPlainTextEdit,
)


class ConversionProgressDialog(QDialog):
    # Emitted when the user cancels - via the Cancel button, Escape, or the
    # window's close button, all of which are treated the same way.
    cancelled = Signal()

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModal)
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        self.status_label = QLabel("Starting…")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.log_toggle_button = QPushButton("Show ffmpeg log ▸")
        self.log_toggle_button.setCheckable(True)
        layout.addWidget(self.log_toggle_button)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(4000)
        mono = QFont("Monospace")
        mono.setStyleHint(QFont.TypeWriter)
        self.log_view.setFont(mono)
        self.log_view.setFixedHeight(220)
        self.log_view.setVisible(False)
        layout.addWidget(self.log_view)

        self.cancel_button = QPushButton("Cancel")
        layout.addWidget(self.cancel_button)

        self.log_toggle_button.toggled.connect(self._on_log_toggled)
        self.cancel_button.clicked.connect(self.reject)

    def _on_log_toggled(self, checked: bool):
        self.log_view.setVisible(checked)
        self.log_toggle_button.setText(
            "Hide ffmpeg log ▾" if checked else "Show ffmpeg log ▸"
        )
        # Force the layout to recompute now rather than on the next event
        # loop turn - querying sizeHint() immediately after a visibility
        # change can otherwise return a stale (pre-change) value, so
        # collapsing wouldn't actually shrink the dialog back down.
        self.layout().activate()
        self.resize(self.width(), self.sizeHint().height())

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_progress(self, pct: float):
        self.progress_bar.setValue(int(pct))

    def append_log(self, text: str):
        self.log_view.appendPlainText(text)

    def reject(self):
        self.cancelled.emit()
        super().reject()
