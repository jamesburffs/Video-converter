"""Alpha channel handling: preserve (restricted to alpha-capable
containers/codecs) vs. flatten onto a matte color."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup, QColorDialog, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QVBoxLayout, QWidget,
)


class AlphaMixin:
    def _build_alpha_group(self) -> QWidget:
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self._section_heading("Alpha channel"))

        self.alpha_status_label = QLabel("No file loaded.")
        layout.addWidget(self.alpha_status_label)

        radio_row = QHBoxLayout()
        self.preserve_alpha_radio = QRadioButton(
            "Preserve alpha (restricts to ProRes 4444 / VP9)"
        )
        self.flatten_alpha_radio = QRadioButton("Flatten onto a matte color")
        self.flatten_alpha_radio.setChecked(True)
        self.alpha_mode_group = QButtonGroup(self)
        self.alpha_mode_group.addButton(self.preserve_alpha_radio)
        self.alpha_mode_group.addButton(self.flatten_alpha_radio)
        radio_row.addWidget(self.preserve_alpha_radio)
        radio_row.addWidget(self.flatten_alpha_radio)
        layout.addLayout(radio_row)

        matte_row = QHBoxLayout()
        matte_row.addWidget(QLabel("Matte color:"))
        self.matte_color_button = QPushButton("Choose Color…")
        self.matte_color_swatch = QLabel()
        self.matte_color_swatch.setFixedSize(28, 20)
        self._update_matte_swatch()
        matte_row.addWidget(self.matte_color_button)
        matte_row.addWidget(self.matte_color_swatch)
        matte_row.addStretch(1)
        layout.addLayout(matte_row)

        return group

    def _on_alpha_mode_changed(self):
        flatten = self.flatten_alpha_radio.isChecked()
        self.matte_color_button.setEnabled(self.source_has_alpha and flatten)
        self._apply_alpha_container_restriction()

    def _on_choose_matte_color(self):
        color = QColorDialog.getColor(self._matte_color, self, "Choose matte color")
        if color.isValid():
            self._matte_color = color
            self._update_matte_swatch()
            self._rebuild_command_preview()

    def _update_matte_swatch(self):
        self.matte_color_swatch.setStyleSheet(
            f"background-color: {self._matte_color.name()}; border: 1px solid gray;"
        )

    def _update_alpha_group_state(self):
        if self._is_batch_mode():
            self.source_has_alpha = any(
                item.media_info and item.media_info.has_alpha for item in self.batch_items
            )
            if self.source_has_alpha:
                self.alpha_status_label.setText(
                    "One or more files in this folder contain an alpha channel."
                )
        else:
            self.source_has_alpha = bool(self.media_info and self.media_info.has_alpha)
            if self.source_has_alpha:
                self.alpha_status_label.setText("Source contains an alpha channel.")

        self.alpha_group.setVisible(self.source_has_alpha)

        for w in (self.preserve_alpha_radio, self.flatten_alpha_radio):
            w.setEnabled(self.source_has_alpha)
        self._on_alpha_mode_changed()
