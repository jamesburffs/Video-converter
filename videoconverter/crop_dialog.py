"""Dialog for visually selecting a crop region from a video preview."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QUrl
from PySide6.QtGui import QColor
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QDialog, QFrame, QGraphicsScene, QGraphicsView, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QSpinBox, QStyle, QVBoxLayout,
)

from .crop_overlay import MIN_CROP, CropOverlayItem
from .video_transport import VideoTransport


class _VideoView(QGraphicsView):
    """Keeps the scene (video item + crop overlay item, both in video-pixel
    coordinates) fitted and letterboxed as the dialog is resized."""

    def _refit(self):
        if self.scene():
            self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refit()

    def showEvent(self, event):
        super().showEvent(event)
        self._refit()


class CropDialog(QDialog):
    def __init__(
        self, video_path: str, video_width: int, video_height: int,
        initial_crop: QRect | None = None, parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Set Crop Area")
        self.resize(900, 680)
        self._video_w = video_width
        self._video_h = video_height
        self._updating_spins = False
        self.result_crop: QRect | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Preview: video/crop handles + scrubber, grouped together ---
        preview_group = QGroupBox()
        preview_layout = QVBoxLayout(preview_group)

        self.scene = QGraphicsScene(0, 0, video_width, video_height, self)
        self.scene.setBackgroundBrush(QColor(20, 20, 20))

        self.video_item = QGraphicsVideoItem()
        self.video_item.setSize(self.scene.sceneRect().size())
        self.scene.addItem(self.video_item)

        self.overlay = CropOverlayItem(video_width, video_height)
        self.scene.addItem(self.overlay)

        self.view = _VideoView(self.scene)
        self.view.setMinimumHeight(420)
        self.view.setFrameShape(QFrame.NoFrame)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        preview_layout.addWidget(self.view, stretch=1)

        self.video_transport = VideoTransport(self.video_item, parent=self)
        self.video_transport.set_source(QUrl.fromLocalFile(video_path))
        self.player = self.video_transport.player
        self.play_button = self.video_transport.play_button
        self.position_slider = self.video_transport.position_slider
        self.time_label = self.video_transport.time_label

        transport_row = QHBoxLayout()
        transport_row.addWidget(self.play_button)
        transport_row.addWidget(self.position_slider, stretch=1)
        transport_row.addWidget(self.time_label)
        preview_layout.addLayout(transport_row)

        layout.addWidget(preview_group, stretch=1)

        # --- Manual crop settings, grouped together with the reset action ---
        settings_group = QGroupBox("Crop Area")
        settings_layout = QHBoxLayout(settings_group)
        settings_layout.addStretch(1)
        self.left_spin = QSpinBox()
        self.top_spin = QSpinBox()
        self.width_spin = QSpinBox()
        self.height_spin = QSpinBox()
        self.left_spin.setRange(0, max(0, video_width - 1))
        self.top_spin.setRange(0, max(0, video_height - 1))
        # Minimums match the overlay's own MIN_CROP floor. If these stayed at
        # 1, every keystroke below 8 would round-trip through the overlay's
        # clamp and get silently forced back up to 8, fighting the user as
        # they type a multi-digit value.
        min_w = min(MIN_CROP, max(1, video_width))
        min_h = min(MIN_CROP, max(1, video_height))
        self.width_spin.setRange(min_w, max(1, video_width))
        self.height_spin.setRange(min_h, max(1, video_height))
        first = True
        for label_text, spin in (
            ("Left:", self.left_spin), ("Top:", self.top_spin),
            ("Width:", self.width_spin), ("Height:", self.height_spin),
        ):
            if not first:
                settings_layout.addSpacing(18)
            first = False
            settings_layout.addWidget(QLabel(label_text))
            settings_layout.addWidget(spin)
        settings_layout.addStretch(1)
        self.reset_full_button = QPushButton("Reset")
        self.reset_full_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton)
        )
        settings_layout.addWidget(self.reset_full_button)
        layout.addWidget(settings_group)

        # --- Save / cancel ---
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.cancel_button = QPushButton("Cancel")
        self.use_button = QPushButton("Use Selection")
        self.use_button.setDefault(True)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.use_button)
        layout.addLayout(actions)

        initial = (
            initial_crop
            if initial_crop and initial_crop.width() > 0 and initial_crop.height() > 0
            else QRect(0, 0, video_width, video_height)
        )
        self.overlay.set_crop(initial.x(), initial.y(), initial.width(), initial.height())
        self._sync_spins_from_crop(self.overlay.crop_rect())

        self.overlay.cropChanged.connect(self._on_overlay_crop_changed)
        for spin in (self.left_spin, self.top_spin, self.width_spin, self.height_spin):
            spin.valueChanged.connect(self._on_spin_changed)

        # Play/pause, scrubbing, and the elapsed/duration label are wired up
        # internally by video_transport (VideoTransport) already.

        self.reset_full_button.clicked.connect(self._on_reset_full)
        self.cancel_button.clicked.connect(self.reject)
        self.use_button.clicked.connect(self._on_use_clicked)

    # ------------------------------------------------------------------
    # Crop rect <-> spin boxes
    # ------------------------------------------------------------------
    def _sync_spins_from_crop(self, r: QRect):
        self._updating_spins = True
        self.left_spin.setValue(r.x())
        self.top_spin.setValue(r.y())
        self.width_spin.setValue(r.width())
        self.height_spin.setValue(r.height())
        self._updating_spins = False

    def _on_overlay_crop_changed(self, x: int, y: int, w: int, h: int):
        self._sync_spins_from_crop(QRect(x, y, w, h))

    def _on_spin_changed(self, *_):
        if self._updating_spins:
            return
        self.overlay.set_crop(
            self.left_spin.value(), self.top_spin.value(),
            self.width_spin.value(), self.height_spin.value(),
        )
        self._sync_spins_from_crop(self.overlay.crop_rect())

    def _on_reset_full(self):
        self.overlay.set_crop(0, 0, self._video_w, self._video_h)
        self._sync_spins_from_crop(self.overlay.crop_rect())

    def _on_use_clicked(self):
        self.result_crop = self.overlay.crop_rect()
        self.accept()

    def closeEvent(self, event):
        self.player.stop()
        event.accept()

    def accept(self):
        self.player.stop()
        super().accept()

    def reject(self):
        self.player.stop()
        super().reject()
