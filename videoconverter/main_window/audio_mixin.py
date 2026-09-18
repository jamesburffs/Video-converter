"""Audio page: keep/re-encode/remove the audio track, codec and bitrate."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QFormLayout, QHBoxLayout, QRadioButton,
    QSpinBox, QVBoxLayout, QWidget,
)


class AudioMixin:
    def _build_audio_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        audio_row = QHBoxLayout()
        self.audio_copy_radio = QRadioButton("Keep original")
        self.audio_encode_radio = QRadioButton("Re-encode")
        self.audio_remove_radio = QRadioButton("Remove")
        self.audio_copy_radio.setChecked(True)
        self.audio_mode_group = QButtonGroup(self)
        for b in (self.audio_copy_radio, self.audio_encode_radio, self.audio_remove_radio):
            self.audio_mode_group.addButton(b)
            audio_row.addWidget(b)
        form.addRow("Audio track:", audio_row)

        self.audio_codec_combo = QComboBox()
        form.addRow("Audio codec:", self.audio_codec_combo)

        self.audio_bitrate_spin = QSpinBox()
        self.audio_bitrate_spin.setRange(32, 1024)
        self.audio_bitrate_spin.setSingleStep(32)
        self.audio_bitrate_spin.setValue(192)
        self.audio_bitrate_spin.setSuffix(" kbps")
        form.addRow("Audio bitrate:", self.audio_bitrate_spin)

        page_layout.addLayout(form)
        page_layout.addStretch(1)
        return page

    def _on_audio_mode_changed(self):
        encode = self.audio_encode_radio.isChecked()
        self.audio_codec_combo.setEnabled(encode)
        self.audio_bitrate_spin.setEnabled(encode)
