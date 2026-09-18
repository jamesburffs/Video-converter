"""Command preview page, settings gathering (the one place all the widget
state across every other page gets collapsed into a ConversionSettings),
and the size estimate."""
from __future__ import annotations

import os

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from .. import probe
from ..command_builder import (
    CONTAINERS, ConversionSettings, build_command, command_to_display_string,
    effective_duration_s, estimate_output_size_bytes,
)


class OutputPreviewMixin:
    def _build_command_preview_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)

        self.command_preview = QPlainTextEdit()
        self.command_preview.setReadOnly(True)
        mono = QFont("Monospace")
        mono.setStyleHint(QFont.TypeWriter)
        self.command_preview.setFont(mono)
        self.command_preview.setFixedHeight(80)
        page_layout.addWidget(self.command_preview)

        self.size_estimate_label = QLabel("Estimated output size: —")
        self.size_estimate_label.setWordWrap(True)
        self.size_estimate_label.setStyleSheet("color: gray;")
        page_layout.addWidget(self.size_estimate_label)

        page_layout.addStretch(1)
        return page

    def _set_convert_button_enabled(self, enabled: bool):
        # Hidden rather than just greyed out when there's nothing to export
        # yet (or a conversion is already running) - a disabled-but-visible
        # button invites clicking it to see why, whereas Start Export only
        # makes sense to show once it would actually do something.
        self.convert_button.setEnabled(enabled)
        self.convert_button.setVisible(enabled)

    def _update_output_controls_enabled(self):
        if self._is_batch_mode():
            has_items = any(i.media_info is not None for i in self.batch_items)
            enabled = has_items and bool(self.batch_dest_folder)
        else:
            enabled = self.media_info is not None
        self._set_convert_button_enabled(enabled)

    # ------------------------------------------------------------------
    # Command building
    # ------------------------------------------------------------------
    def _gather_settings(
        self, output_path: str = "", media_info: probe.MediaInfo | None = None
    ) -> ConversionSettings:
        info = media_info if media_info is not None else self.media_info
        container_key = self.container_combo.currentText()
        source_w = info.video.width if (info and info.video) else 0
        source_h = info.video.height if (info and info.video) else 0

        # Size/Crop is hidden in the UI when a batch's source files aren't
        # all the same frame size (see _update_crop_controls_enabled) - a
        # single absolute-pixel crop, or resolution target, applied
        # uniformly to every file wouldn't mean the same thing for each of
        # them. Enforced here too, not just in the UI, so a crop/resolution
        # set before a differently-sized file joined the batch doesn't
        # silently keep applying to it once the setting's no longer even
        # visible to change.
        size_crop_available = not self._is_batch_mode() or self._batch_video_dims_consistent()

        crop_enabled = False
        crop_x = crop_y = crop_w = crop_h = 0
        if size_crop_available and self._crop_rect and source_w > 0 and source_h > 0:
            crop_enabled = True
            crop_x = min(self._crop_rect.x(), source_w - 1)
            crop_y = min(self._crop_rect.y(), source_h - 1)
            crop_w = min(self._crop_rect.width(), source_w - crop_x)
            crop_h = min(self._crop_rect.height(), source_h - crop_y)

        trim_range = self.trim_panel.trim_range_seconds()
        trim_enabled = False
        trim_start_s = trim_end_s = 0.0
        if trim_range and info and info.duration_s > 0:
            start = max(0.0, min(trim_range[0], info.duration_s))
            end = max(0.0, min(trim_range[1], info.duration_s))
            if end > start:
                trim_enabled = True
                trim_start_s = start
                trim_end_s = end

        return ConversionSettings(
            input_path=info.path if info else "",
            output_path=output_path,
            container=container_key,
            video_codec=self._current_video_codec(),
            quality_mode="crf" if self.crf_radio.isChecked() else "bitrate",
            crf=self.crf_spin.value(),
            video_bitrate_kbps=self.bitrate_spin.value(),
            preset=self.preset_combo.currentText(),
            resolution_mode=(
                self.resolution_combo.currentText() if size_crop_available else "Source"
            ),
            custom_width=self.custom_width_spin.value(),
            custom_height=self.custom_height_spin.value(),
            keep_aspect=self.keep_aspect_check.isChecked(),
            fps_mode=self.fps_combo.currentText(),
            custom_fps=self.custom_fps_spin.value(),
            audio_mode=(
                "copy" if self.audio_copy_radio.isChecked()
                else "remove" if self.audio_remove_radio.isChecked()
                else "encode"
            ),
            audio_codec=self.audio_codec_combo.currentData() or "aac",
            audio_bitrate_kbps=self.audio_bitrate_spin.value(),
            faststart=self.faststart_check.isChecked(),
            source_width=source_w,
            source_height=source_h,
            source_has_alpha=bool(info and info.has_alpha),
            alpha_mode="preserve" if self.preserve_alpha_radio.isChecked() else "flatten",
            matte_color=self._matte_color.name(),
            crop_enabled=crop_enabled,
            crop_x=crop_x,
            crop_y=crop_y,
            crop_w=crop_w,
            crop_h=crop_h,
            trim_enabled=trim_enabled,
            trim_start_s=trim_start_s,
            trim_end_s=trim_end_s,
        )

    def _schedule_command_preview_rebuild(self, *_):
        self._preview_timer.start()

    def _rebuild_command_preview(self, *_):
        container_key = self.container_combo.currentText()
        ext = CONTAINERS[container_key]["ext"]

        if self._is_batch_mode():
            sample = next((i for i in self.batch_items if i.media_info is not None), None)
            if sample is None:
                self.command_preview.setPlainText(
                    "ffmpeg command will be shown once a source folder is scanned…"
                )
                self.size_estimate_label.setText("Estimated total output size: —")
                return
            output_path = os.path.join(
                self.batch_dest_folder or "<destination folder>",
                os.path.splitext(os.path.basename(sample.input_path))[0] + f".{ext}",
            )
            settings = self._gather_settings(output_path, media_info=sample.media_info)
        else:
            input_path = self.media_info.path if self.media_info else "<input file>"
            placeholder_output = self._suggest_output_path(input_path, ext)
            settings = self._gather_settings(placeholder_output)
            if not self.media_info:
                settings.input_path = input_path

        cmd = build_command(settings)
        prefix = "First file: " if self._is_batch_mode() else ""
        self.command_preview.setPlainText(prefix + command_to_display_string(cmd))
        self._update_size_estimate()

    def _update_size_estimate(self):
        if self._is_batch_mode():
            items = [i for i in self.batch_items if i.media_info is not None]
            if not items:
                self.size_estimate_label.setText("Estimated total output size: —")
                return
            total = 0
            any_known = False
            any_unknown = False
            for item in items:
                mi = item.media_info
                settings = self._gather_settings(item.output_path, media_info=mi)
                est = estimate_output_size_bytes(
                    settings, effective_duration_s(settings, mi.duration_s),
                    source_fps=mi.video.fps if mi.video else 30.0,
                    source_size_bytes=mi.size_bytes,
                    source_audio_bit_rate=mi.audio.bit_rate if mi.audio else None,
                    source_has_audio=mi.has_audio,
                )
                if est is None:
                    any_unknown = True
                else:
                    any_known = True
                    total += est
            if not any_known:
                self.size_estimate_label.setText(
                    "Estimated total output size: not available for this codec"
                )
            else:
                suffix = " (some files not estimated)" if any_unknown else ""
                self.size_estimate_label.setText(
                    f"Estimated total output size: ~{probe.human_size(total)}{suffix}"
                    "  ·  rough guide only, actual size depends on content"
                )
        else:
            if not self.media_info:
                self.size_estimate_label.setText("Estimated output size: —")
                return
            mi = self.media_info
            settings = self._gather_settings(media_info=mi)
            est = estimate_output_size_bytes(
                settings, effective_duration_s(settings, mi.duration_s),
                source_fps=mi.video.fps if mi.video else 30.0,
                source_size_bytes=mi.size_bytes,
                source_audio_bit_rate=mi.audio.bit_rate if mi.audio else None,
                source_has_audio=mi.has_audio,
            )
            if est is None:
                self.size_estimate_label.setText(
                    "Estimated output size: not available for this codec"
                )
            else:
                self.size_estimate_label.setText(
                    f"Estimated output size: ~{probe.human_size(est)}"
                    "  ·  rough guide only, actual size depends on content"
                )

    def _suggest_output_path(self, input_path: str, ext: str) -> str:
        if not input_path or input_path == "<input file>":
            return f"<output file>.{ext}"
        base, _ = os.path.splitext(input_path)
        return f"{base}_converted.{ext}"
