"""Settings profiles: the profile row above the source tabs, and
save/load/update/delete."""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtCore import QRect
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton,
    QWidget,
)

from .. import profiles


class ProfilesMixin:
    def _build_profile_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Profile:"))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(200)
        self.load_profile_button = QPushButton("Load")
        self.update_profile_button = QPushButton("Update")
        self.save_profile_button = QPushButton("Save As…")
        self.delete_profile_button = QPushButton("Delete")
        layout.addWidget(self.profile_combo, stretch=1)
        layout.addWidget(self.load_profile_button)
        layout.addWidget(self.update_profile_button)
        layout.addWidget(self.save_profile_button)
        layout.addWidget(self.delete_profile_button)
        return row

    def _refresh_profile_combo(self, select: str | None = None):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("— Select profile —")
        for name in profiles.list_profiles():
            self.profile_combo.addItem(name)
        if select:
            idx = self.profile_combo.findText(select)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
        self.profile_combo.blockSignals(False)
        self._on_profile_selection_changed()

    def _on_profile_selection_changed(self):
        has_selection = self.profile_combo.currentIndex() > 0
        self.load_profile_button.setEnabled(has_selection)
        self.delete_profile_button.setEnabled(has_selection)
        # Update overwrites whichever profile was last actually loaded, so
        # merely browsing the dropdown to a different entry (without
        # clicking Load) shouldn't leave it enabled - that could silently
        # overwrite the wrong profile.
        self._profile_loaded = False
        self.update_profile_button.setEnabled(False)

    def _on_save_profile_clicked(self):
        name, ok = QInputDialog.getText(self, "Save profile", "Profile name:")
        if not ok or not name.strip():
            return
        settings = self._gather_settings()
        saved_name = profiles.save_profile(name.strip(), settings)
        self._refresh_profile_combo(select=saved_name)
        self.status_label.setText(f"Saved profile '{saved_name}'.")

    def _on_update_profile_clicked(self):
        if self.profile_combo.currentIndex() <= 0:
            return
        name = self.profile_combo.currentText()
        settings = self._gather_settings()
        profiles.save_profile(name, settings)
        self.status_label.setText(f"Updated profile '{name}'.")

    def _on_load_profile_clicked(self):
        if self.profile_combo.currentIndex() <= 0:
            return
        name = self.profile_combo.currentText()
        try:
            data = profiles.load_profile(name)
        except OSError as exc:
            QMessageBox.warning(self, "Could not load profile", str(exc))
            return
        self._apply_profile_data(data)
        self._profile_loaded = True
        self.update_profile_button.setEnabled(True)
        self.status_label.setText(f"Loaded profile '{name}'.")

    def _on_delete_profile_clicked(self):
        if self.profile_combo.currentIndex() <= 0:
            return
        name = self.profile_combo.currentText()
        reply = QMessageBox.question(
            self, "Delete profile", f"Delete profile '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        profiles.delete_profile(name)
        self._refresh_profile_combo()

    def _apply_profile_data(self, data: dict):
        # Alpha mode first, since it can restrict container/codec choices.
        if data.get("alpha_mode") == "preserve":
            self.preserve_alpha_radio.setChecked(True)
        else:
            self.flatten_alpha_radio.setChecked(True)
        if data.get("matte_color"):
            self._matte_color = QColor(data["matte_color"])
            self._update_matte_swatch()

        if data.get("container"):
            self.container_combo.setCurrentText(data["container"])
        if data.get("video_codec"):
            idx = self.video_codec_combo.findData(data["video_codec"])
            if idx >= 0:
                self.video_codec_combo.setCurrentIndex(idx)

        if data.get("quality_mode") == "bitrate":
            self.bitrate_radio.setChecked(True)
        else:
            self.crf_radio.setChecked(True)
        self.crf_spin.setValue(data.get("crf", 23))
        self.bitrate_spin.setValue(data.get("video_bitrate_kbps", 4000))
        if data.get("preset"):
            self.preset_combo.setCurrentText(data["preset"])
        if data.get("resolution_mode"):
            self.resolution_combo.setCurrentText(data["resolution_mode"])
        self.custom_width_spin.setValue(data.get("custom_width", 1920))
        self.keep_aspect_check.setChecked(data.get("keep_aspect", True))
        if not self.keep_aspect_check.isChecked():
            self.custom_height_spin.setValue(data.get("custom_height", 1080))
        if data.get("fps_mode"):
            self.fps_combo.setCurrentText(data["fps_mode"])
        self.custom_fps_spin.setValue(data.get("custom_fps", 30.0))

        mode = data.get("audio_mode", "copy")
        if mode == "encode":
            self.audio_encode_radio.setChecked(True)
        elif mode == "remove":
            self.audio_remove_radio.setChecked(True)
        else:
            self.audio_copy_radio.setChecked(True)
        if data.get("audio_codec"):
            idx = self.audio_codec_combo.findData(data["audio_codec"])
            if idx >= 0:
                self.audio_codec_combo.setCurrentIndex(idx)
        self.audio_bitrate_spin.setValue(data.get("audio_bitrate_kbps", 192))
        self.faststart_check.setChecked(data.get("faststart", False))

        if data.get("crop_enabled") and data.get("crop_w") and data.get("crop_h"):
            self._crop_rect = QRect(
                data.get("crop_x", 0), data.get("crop_y", 0),
                data.get("crop_w", 0), data.get("crop_h", 0),
            )
        else:
            self._crop_rect = None
        self._update_crop_status()
        self._update_computed_height()
        self._refresh_crop_preview()
        self._update_trim_crop_view()

        self._rebuild_command_preview()
