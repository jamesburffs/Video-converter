"""Container/codec page: container, video codec, quality mode (CRF or
bitrate), encoder preset, frame rate - and the alpha-driven restriction of
which containers/codecs are offered (see alpha_mixin.py for the alpha
controls themselves)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QRadioButton, QSpinBox, QVBoxLayout, QWidget,
)

from ..command_builder import (
    ALPHA_CONTAINERS, AUDIO_CODEC_LABELS, CONTAINER_ALPHA_CODEC, CONTAINERS,
    CRF_CODECS, VIDEO_CODEC_LABELS, X264_X265_PRESETS,
)
from ..widgets import NoWheelSlider

ALL_CONTAINERS = list(CONTAINERS.keys())


class CodecContainerMixin:
    def _build_codec_container_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        # Container
        self.container_combo = QComboBox()
        form.addRow("Container:", self.container_combo)

        # Video codec
        self.video_codec_combo = QComboBox()
        form.addRow("Video codec:", self.video_codec_combo)

        # Quality mode
        quality_row = QHBoxLayout()
        self.crf_radio = QRadioButton("Quality (CRF)")
        self.bitrate_radio = QRadioButton("Target bitrate")
        self.crf_radio.setChecked(True)
        self.quality_mode_group = QButtonGroup(self)
        self.quality_mode_group.addButton(self.crf_radio)
        self.quality_mode_group.addButton(self.bitrate_radio)
        quality_row.addWidget(self.crf_radio)
        quality_row.addWidget(self.bitrate_radio)
        form.addRow("Quality mode:", quality_row)

        self.crf_slider = NoWheelSlider(Qt.Horizontal)
        self.crf_slider.setRange(0, 63)
        self.crf_slider.setValue(23)
        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 63)
        self.crf_spin.setValue(23)
        crf_row = QHBoxLayout()
        crf_row.addWidget(self.crf_slider, stretch=1)
        crf_row.addWidget(self.crf_spin)
        form.addRow("CRF value:", crf_row)
        self.crf_hint = QLabel("Lower = higher quality/larger file. Typical: 18-28.")
        self.crf_hint.setStyleSheet("color: gray;")
        form.addRow("", self.crf_hint)

        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(100, 100000)
        self.bitrate_spin.setSingleStep(100)
        self.bitrate_spin.setValue(4000)
        self.bitrate_spin.setSuffix(" kbps")
        form.addRow("Video bitrate:", self.bitrate_spin)

        # Preset
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(X264_X265_PRESETS)
        self.preset_combo.setCurrentText("medium")
        form.addRow("Encoder preset:", self.preset_combo)

        # Frame rate
        fps_row = QHBoxLayout()
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["Source", "Custom"])
        self.custom_fps_spin = QDoubleSpinBox()
        self.custom_fps_spin.setRange(1.0, 240.0)
        self.custom_fps_spin.setValue(30.0)
        fps_row.addWidget(self.fps_combo)
        fps_row.addWidget(self.custom_fps_spin)
        form.addRow("Frame rate:", fps_row)

        # Faststart
        self.faststart_check = QCheckBox(
            "Enable fast start (move index to front of file, good for web streaming)"
        )
        form.addRow("", self.faststart_check)

        page_layout.addLayout(form)

        # Alpha channel handling affects which containers/codecs are
        # available, so it lives on the same page as those settings.
        self.alpha_group = self._build_alpha_group()
        page_layout.addWidget(self.alpha_group)

        page_layout.addStretch(1)
        return page

    def _apply_alpha_container_restriction(self):
        preserve = self.source_has_alpha and self.preserve_alpha_radio.isChecked()
        current = self.container_combo.currentText()
        items = ALPHA_CONTAINERS if preserve else ALL_CONTAINERS

        self.container_combo.blockSignals(True)
        self.container_combo.clear()
        self.container_combo.addItems(items)
        if current in items:
            self.container_combo.setCurrentText(current)
        else:
            self.container_combo.setCurrentIndex(0)
        self.container_combo.blockSignals(False)

        self._refresh_codec_choices()

    def _refresh_codec_choices(self):
        container_key = self.container_combo.currentText()
        info = CONTAINERS[container_key]
        preserve = self.source_has_alpha and self.preserve_alpha_radio.isChecked()

        self.video_codec_combo.blockSignals(True)
        self.video_codec_combo.clear()
        codecs = info["video_codecs"]
        if preserve:
            alpha_codec = CONTAINER_ALPHA_CODEC.get(container_key)
            codecs = [c for c in codecs if c == alpha_codec]
        for codec in codecs:
            self.video_codec_combo.addItem(VIDEO_CODEC_LABELS[codec], codec)
        self.video_codec_combo.blockSignals(False)

        self.audio_codec_combo.blockSignals(True)
        self.audio_codec_combo.clear()
        for codec in info["audio_codecs"]:
            if codec == "copy":
                continue  # "copy" is handled by the Keep-original radio button
            self.audio_codec_combo.addItem(AUDIO_CODEC_LABELS[codec], codec)
        self.audio_codec_combo.blockSignals(False)

        self.faststart_check.setEnabled(info["supports_faststart"])
        if not info["supports_faststart"]:
            self.faststart_check.setChecked(False)

        self._on_video_codec_changed()

    def _current_video_codec(self) -> str:
        return self.video_codec_combo.currentData() or "libx264"

    def _on_container_changed(self):
        self._refresh_codec_choices()

    def _on_video_codec_changed(self):
        codec = self._current_video_codec()
        is_copy = codec == "copy"
        has_rate_control = codec in CRF_CODECS

        for w in (self.fps_combo, self.custom_fps_spin):
            w.setEnabled(not is_copy)

        for w in (self.crf_radio, self.bitrate_radio):
            w.setEnabled(has_rate_control)

        crf_max = 63 if codec == "libvpx-vp9" else 51
        self.crf_spin.setMaximum(crf_max)
        self.crf_slider.setMaximum(crf_max)
        self.preset_combo.setVisible(codec in ("libx264", "libx265"))
        self._on_quality_mode_changed()
        self._on_resolution_changed()
        self._update_crop_controls_enabled()

    def _on_quality_mode_changed(self):
        use_crf = self.crf_radio.isChecked() and self.crf_radio.isEnabled()
        for w in (self.crf_slider, self.crf_spin, self.crf_hint):
            w.setEnabled(use_crf)
        self.bitrate_spin.setEnabled(not use_crf and self.bitrate_radio.isEnabled())

    def _refresh_resolution_ui_state(self):
        codec_is_copy = self._current_video_codec() == "copy"
        self.resolution_combo.setEnabled(not codec_is_copy)
        is_custom = self.resolution_combo.currentText() == "Custom" and not codec_is_copy
        self.custom_res_row_widget.setEnabled(is_custom)
        self.custom_height_spin.setEnabled(is_custom and not self.keep_aspect_check.isChecked())

    def _on_resolution_changed(self):
        self._refresh_resolution_ui_state()
        self._update_computed_height()

    def _on_fps_mode_changed(self):
        self.custom_fps_spin.setEnabled(
            self.fps_combo.currentText() == "Custom" and self.fps_combo.isEnabled()
        )

    def _on_crf_slider_changed(self, value: int):
        if self.crf_spin.value() != value:
            self.crf_spin.blockSignals(True)
            self.crf_spin.setValue(value)
            self.crf_spin.blockSignals(False)

    def _on_crf_spin_changed(self, value: int):
        if self.crf_slider.value() != value:
            self.crf_slider.blockSignals(True)
            self.crf_slider.setValue(value)
            self.crf_slider.blockSignals(False)
