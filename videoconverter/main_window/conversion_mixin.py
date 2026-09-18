"""Convert/cancel dispatch, the progress dialog, and single-file + batch
conversion execution."""
from __future__ import annotations

import os

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QMessageBox

from .. import batch
from ..command_builder import (
    CONTAINERS, build_command, command_to_display_string, effective_duration_s,
)
from ..converter import ConversionRunner
from ..progress_dialog import ConversionProgressDialog


class ConversionMixin:
    def _on_convert_clicked(self):
        if self._is_batch_mode():
            self._start_batch_conversion()
        else:
            self._start_single_conversion()

    def _on_cancel_clicked(self):
        self._cancel_requested = True
        if self.runner:
            self.status_label.setText("Cancelling…")
            self.runner.cancel()

    def _set_running_state(self, running: bool):
        self._set_convert_button_enabled(not running)
        self.select_file_button.setEnabled(not running)
        self.select_folder_button.setEnabled(not running)

    def _open_progress_dialog(self, title: str) -> ConversionProgressDialog:
        self._last_log_lines = []
        dialog = ConversionProgressDialog(title, self)
        dialog.cancelled.connect(self._on_cancel_clicked)
        self._progress_dialog = dialog
        dialog.show()
        return dialog

    def _close_progress_dialog(self):
        if self._progress_dialog:
            self._progress_dialog.accept()
            self._progress_dialog = None

    def _append_log_line(self, text: str):
        self._last_log_lines.append(text)
        if self._progress_dialog:
            self._progress_dialog.append_log(text)

    def _save_log_to_file(self, text: str):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save ffmpeg log", "ffmpeg-log.txt",
            "Text files (*.txt);;All files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return
        try:
            with open(path, "w") as f:
                f.write(text)
        except OSError as exc:
            QMessageBox.warning(self, "Could not save log", str(exc))

    def _show_conversion_failed_dialog(self, message: str):
        box = QMessageBox(self)
        box.setWindowTitle("Conversion Failed")
        box.setIcon(QMessageBox.Critical)
        box.setText(message)
        save_btn = box.addButton("Save Log…", QMessageBox.ActionRole)
        close_btn = box.addButton("Close", QMessageBox.RejectRole)
        box.setDefaultButton(close_btn)
        box.exec()
        if box.clickedButton() is save_btn:
            self._save_log_to_file("\n".join(self._last_log_lines))

    # ------------------------------------------------------------------
    # Single-file conversion
    # ------------------------------------------------------------------
    def _start_single_conversion(self):
        if not self.media_info:
            return
        container_key = self.container_combo.currentText()
        ext = CONTAINERS[container_key]["ext"]
        suggested = self._suggest_output_path(self.media_info.path, ext)

        path, _ = QFileDialog.getSaveFileName(
            self, "Save converted file as", suggested, f"*.{ext}",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return
        if not path.lower().endswith(f".{ext}"):
            path += f".{ext}"

        if os.path.abspath(path) == os.path.abspath(self.media_info.path):
            QMessageBox.warning(
                self, "Invalid output",
                "The output file cannot be the same as the input file.",
            )
            return

        settings = self._gather_settings(path)
        command = build_command(settings)

        self._cancel_requested = False
        self._last_output_path = path
        self.status_label.setText("Converting…")
        self._set_running_state(True)

        dialog = self._open_progress_dialog("Converting…")
        dialog.set_status(f"Converting {os.path.basename(self.media_info.path)}…")
        self._append_log_line(command_to_display_string(command))

        self.runner = ConversionRunner(
            effective_duration_s(settings, self.media_info.duration_s), self
        )
        self.runner.progress.connect(self._on_progress)
        self.runner.log_line.connect(self._append_log_line)
        self.runner.finished.connect(self._on_conversion_finished)
        self.runner.start(command)

    def _on_progress(self, pct: float):
        if self._progress_dialog:
            self._progress_dialog.set_progress(pct)

    def _on_conversion_finished(self, success: bool, message: str):
        self._set_running_state(False)
        self._close_progress_dialog()
        self.status_label.setText(message)
        if success:
            self._notify(
                "Conversion complete",
                f"Saved to {os.path.basename(self._last_output_path)}",
            )
            self._show_single_completion_dialog(self._last_output_path)
        elif "cancelled" not in message.lower():
            self._notify("Conversion failed", message, warning=True)
            self._show_conversion_failed_dialog(message)
        self.runner = None

    def _show_single_completion_dialog(self, output_path: str):
        box = QMessageBox(self)
        box.setWindowTitle("Conversion finished")
        box.setIcon(QMessageBox.Information)
        box.setText(f"Saved to:\n{output_path}")
        open_video_btn = box.addButton("Open Video", QMessageBox.ActionRole)
        open_folder_btn = box.addButton("Open Folder", QMessageBox.ActionRole)
        convert_another_btn = box.addButton("Convert Another File…", QMessageBox.ActionRole)
        close_btn = box.addButton("Close", QMessageBox.RejectRole)
        box.setDefaultButton(close_btn)
        box.exec()

        clicked = box.clickedButton()
        if clicked is open_video_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(output_path))
        elif clicked is open_folder_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(output_path)))
        elif clicked is convert_another_btn:
            self._on_select_file()

    # ------------------------------------------------------------------
    # Batch conversion
    # ------------------------------------------------------------------
    def _start_batch_conversion(self):
        valid_items = [i for i in self.batch_items if i.media_info is not None]
        if not valid_items or not self.batch_dest_folder:
            return

        container_key = self.container_combo.currentText()
        ext = CONTAINERS[container_key]["ext"]
        batch.assign_output_paths(valid_items, self.batch_dest_folder, ext)

        for item in valid_items:
            item.status = batch.ItemStatus.PENDING
            item.error = ""
            self._refresh_queue_row(item)

        self._batch_queue = valid_items
        self._batch_index = -1
        self._cancel_requested = False
        self._set_running_state(True)
        self._open_progress_dialog("Converting Batch…")
        self._advance_batch()

    def _advance_batch(self):
        self._batch_index += 1
        total = len(self._batch_queue)
        if self._batch_index >= total:
            self._set_running_state(False)
            self._close_progress_dialog()
            done = sum(1 for i in self._batch_queue if i.status == batch.ItemStatus.DONE)
            failed = sum(1 for i in self._batch_queue if i.status == batch.ItemStatus.FAILED)
            msg = f"Batch complete: {done} converted, {failed} failed."
            self.status_label.setText(msg)
            self._notify("Batch conversion complete", msg, warning=(failed > 0 and done == 0))
            self._show_batch_completion_dialog(msg, had_failures=failed > 0)
            self.runner = None
            return

        item = self._batch_queue[self._batch_index]
        item.status = batch.ItemStatus.CONVERTING
        self._refresh_queue_row(item)

        settings = self._gather_settings(item.output_path, media_info=item.media_info)
        command = build_command(settings)

        status_text = (
            f"Converting {self._batch_index + 1}/{total}: {os.path.basename(item.input_path)}"
        )
        self.status_label.setText(status_text)
        if self._progress_dialog:
            self._progress_dialog.set_status(status_text)
        self._append_log_line(f"\n--- {os.path.basename(item.input_path)} ---")
        self._append_log_line(command_to_display_string(command))

        self.runner = ConversionRunner(
            effective_duration_s(settings, item.media_info.duration_s), self
        )
        self.runner.progress.connect(self._on_batch_progress)
        self.runner.log_line.connect(self._append_log_line)
        self.runner.finished.connect(
            lambda success, msg, item=item: self._on_batch_item_finished(item, success, msg)
        )
        self.runner.start(command)

    def _on_batch_progress(self, pct: float):
        total = len(self._batch_queue)
        if total == 0:
            return
        overall = (self._batch_index + pct / 100.0) / total * 100.0
        if self._progress_dialog:
            self._progress_dialog.set_progress(overall)

    def _on_batch_item_finished(self, item: batch.BatchItem, success: bool, message: str):
        item.status = batch.ItemStatus.DONE if success else batch.ItemStatus.FAILED
        item.error = "" if success else message
        self._refresh_queue_row(item)

        if self._cancel_requested:
            self._set_running_state(False)
            self._close_progress_dialog()
            self.status_label.setText("Batch cancelled.")
            self.runner = None
            return

        self._advance_batch()

    def _show_batch_completion_dialog(self, message: str, had_failures: bool = False):
        box = QMessageBox(self)
        box.setWindowTitle("Batch conversion finished")
        box.setIcon(QMessageBox.Warning if had_failures else QMessageBox.Information)
        box.setText(message)
        open_folder_btn = None
        if self.batch_dest_folder:
            open_folder_btn = box.addButton("Open Destination Folder", QMessageBox.ActionRole)
        save_log_btn = box.addButton("Save Log…", QMessageBox.ActionRole) if had_failures else None
        close_btn = box.addButton("Close", QMessageBox.RejectRole)
        box.setDefaultButton(close_btn)
        box.exec()

        clicked = box.clickedButton()
        if open_folder_btn is not None and clicked is open_folder_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.batch_dest_folder))
        elif save_log_btn is not None and clicked is save_log_btn:
            self._save_log_to_file("\n".join(self._last_log_lines))
