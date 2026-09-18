"""Dialog that offers to install ffmpeg when it's missing from PATH."""
from __future__ import annotations

from PySide6.QtCore import QProcess, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit,
)

from . import probe
from .external_env import clean_qprocess_environment
from .ffmpeg_installer import InstallPlan, detect_install_plan


class FFmpegSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FFmpeg Setup")
        self.resize(560, 320)
        self._process: QProcess | None = None
        self.plan: InstallPlan = detect_install_plan()

        layout = QVBoxLayout(self)

        header = QLabel(
            "This tool needs ffmpeg and ffprobe, but they weren't found on your "
            "system PATH."
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        self.plan_label = QLabel(self.plan.description)
        self.plan_label.setWordWrap(True)
        layout.addWidget(self.plan_label)

        if self.plan.manual_instructions:
            manual_label = QLabel(self.plan.manual_instructions)
            manual_label.setWordWrap(True)
            manual_label.setStyleSheet("color: gray;")
            layout.addWidget(manual_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        mono = QFont("Monospace")
        mono.setStyleHint(QFont.TypeWriter)
        self.log_view.setFont(mono)
        self.log_view.setVisible(False)
        layout.addWidget(self.log_view)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        button_row = QHBoxLayout()
        self.install_button = QPushButton("Install FFmpeg")
        self.install_button.setVisible(self.plan.command is not None)
        self.download_button = QPushButton(self.plan.download_label)
        self.close_button = QPushButton("Close")
        button_row.addWidget(self.install_button)
        button_row.addWidget(self.download_button)
        button_row.addStretch(1)
        button_row.addWidget(self.close_button)
        layout.addLayout(button_row)

        self.install_button.clicked.connect(self._on_install_clicked)
        self.download_button.clicked.connect(self._on_download_clicked)
        self.close_button.clicked.connect(self._on_close_clicked)

    def _on_download_clicked(self):
        QDesktopServices.openUrl(QUrl(self.plan.download_url))

    def _on_install_clicked(self):
        if not self.plan.command:
            return
        self.install_button.setEnabled(False)
        self.log_view.setVisible(True)
        self.log_view.clear()
        self.status_label.setText("Installing…")

        self._process = QProcess(self)
        self._process.setProcessEnvironment(clean_qprocess_environment())
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.setProgram(self.plan.command[0])
        self._process.setArguments(self.plan.command[1:])
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)
        self._process.start()

    def _on_output(self):
        if not self._process:
            return
        chunk = bytes(self._process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        if chunk:
            self.log_view.appendPlainText(chunk.rstrip())

    def _on_finished(self, exit_code: int, _exit_status):
        found = probe.ffmpeg_available() and probe.ffprobe_available()
        if found:
            self.status_label.setText("ffmpeg is now available. You're all set.")
            self.install_button.setVisible(False)
        else:
            self.status_label.setText(
                f"Install command exited with code {exit_code}, and ffmpeg still "
                "isn't on your PATH. See the log above, or install manually."
            )
            self.install_button.setEnabled(True)

    def _on_error(self, error):
        self.status_label.setText(f"Could not run install command: {error}")
        self.install_button.setEnabled(True)

    def _on_close_clicked(self):
        self.accept()

    def closeEvent(self, event):
        if self._process and self._process.state() != QProcess.NotRunning:
            self._process.kill()
        event.accept()
