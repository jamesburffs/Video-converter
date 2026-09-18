"""The Trim detail page: its own preview player, scrubber, in/out controls
and trim-selection state, pulled out of MainWindow since - unlike most of
the other detail pages, which are mostly static forms - Trim carries a
real chunk of self-contained behavior (a video preview synced to a
TrimRange, frame-accurate timecode fields, crop mirroring) that doesn't
need to reach into the rest of the window.

MainWindow drives this through a narrow surface: set_source() when the
selected file/batch sample changes, set_crop() to mirror the Size/Crop
page's active crop, trim_range_seconds() to read the current selection
when building the ffmpeg command, and stop_playback() on window close.
Everything else - the preview scene, the transport, the in/out buttons and
fields, TrimRange - is this class's own business.
"""
from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, QSize, QSizeF, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QFrame, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QPushButton,
    QStyle, QVBoxLayout, QWidget,
)

from . import icon_factory, probe
from .crop_overlay import CropMaskItem
from .theme import DIVIDER_COLOR
from .trim_bar import MIN_GAP, TimecodeEdit, TrimRange, TrimScrubberSlider
from .video_transport import VideoTransport


class _FitVideoView(QGraphicsView):
    """Keeps its scene (a QGraphicsVideoItem sized to the video's own pixel
    dimensions) fitted and letterboxed as the view is resized. Normally
    fits the whole scene, but set_focus_rect() can point it at a sub-rect
    instead (e.g. the active crop) so playback zooms in on just that area."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._focus_rect: QRectF | None = None

    def set_focus_rect(self, rect: QRectF | None):
        self._focus_rect = rect
        self._refit()

    def _refit(self):
        if self.scene():
            target = self._focus_rect if self._focus_rect is not None else self.scene().sceneRect()
            self.fitInView(target, Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refit()

    def showEvent(self, event):
        super().showEvent(event)
        self._refit()


class TrimPanel(QWidget):
    # Emitted whenever the trim selection changes for any reason (drag,
    # Set/Go-to buttons, typed field, Reset) - the caller should rebuild
    # its ffmpeg command preview in response.
    settingsChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Whatever set_source() was last given - the one source of truth
        # this panel's internal handlers (and set_crop(), independently of
        # whether the controls are currently enabled) read from, mirroring
        # what MainWindow's _current_crop_media_info() would return at the
        # time set_source() was called.
        self._source_info: probe.MediaInfo | None = None
        # (start_s, end_s) relative to the source's own duration, or None
        # for no trim (full clip).
        self._trim_range: tuple[float, float] | None = None

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)

        preview_group = QWidget()
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self.trim_scene = QGraphicsScene(0, 0, 16, 9, self)
        self.trim_scene.setBackgroundBrush(QColor(20, 20, 20))
        self.trim_video_item = QGraphicsVideoItem()
        self.trim_scene.addItem(self.trim_video_item)
        self.trim_crop_mask = CropMaskItem(1, 1)
        self.trim_scene.addItem(self.trim_crop_mask)

        self.trim_view = _FitVideoView(self.trim_scene)
        self.trim_view.setMinimumHeight(260)
        self.trim_view.setFrameShape(QFrame.NoFrame)
        self.trim_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.trim_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        preview_layout.addWidget(self.trim_view, stretch=1)

        # Pure state - the scrubber mask, the in/out fields and command
        # building all read from/write to this one place.
        self.trim_range = TrimRange(self)

        # Owns the player plus the play button/scrubber/label wiring (see
        # VideoTransport) - CropDialog uses the same class for its own
        # preview. The scrubber here is a TrimScrubberSlider (rather than
        # the default plain one) since it also paints the trim mask, so the
        # trimmed region is visible right where you're scrubbing; it's
        # added full-width in its own row directly under the preview, while
        # the play button and label join the other trim controls below.
        self.trim_transport = VideoTransport(
            self.trim_video_item, icon_button=True,
            slider=TrimScrubberSlider(Qt.Horizontal), parent=self,
        )
        self.trim_player = self.trim_transport.player
        self.trim_position_slider = self.trim_transport.position_slider
        self.trim_play_button = self.trim_transport.play_button
        self.trim_position_slider.setEnabled(False)
        preview_layout.addWidget(self.trim_position_slider)

        icon_color = self.palette().color(QPalette.ButtonText)
        icon_size = QSize(15, 15)

        self.trim_play_button.setIconSize(icon_size)
        self.trim_play_button.setEnabled(False)

        self.trim_set_in_button = QPushButton()
        self.trim_set_in_button.setIcon(icon_factory.trim_bound_icon("start", icon_color))
        self.trim_set_in_button.setIconSize(icon_size)
        self.trim_set_in_button.setToolTip("Set in-point at the current position")
        self.trim_set_in_button.setEnabled(False)
        self.trim_in_edit = TimecodeEdit()
        self.trim_in_edit.setFixedWidth(84)
        self.trim_in_edit.setToolTip(
            "In-point (H:MM:SS:FF) - drag to nudge, click to type"
        )
        self.trim_in_edit.setEnabled(False)

        self.trim_goto_in_button = QPushButton()
        self.trim_goto_in_button.setIcon(icon_factory.trim_goto_icon("start", icon_color))
        self.trim_goto_in_button.setIconSize(icon_size)
        self.trim_goto_in_button.setToolTip("Go to in-point")
        self.trim_goto_in_button.setEnabled(False)

        self.trim_goto_out_button = QPushButton()
        self.trim_goto_out_button.setIcon(icon_factory.trim_goto_icon("end", icon_color))
        self.trim_goto_out_button.setIconSize(icon_size)
        self.trim_goto_out_button.setToolTip("Go to out-point")
        self.trim_goto_out_button.setEnabled(False)

        self.trim_set_out_button = QPushButton()
        self.trim_set_out_button.setIcon(icon_factory.trim_bound_icon("end", icon_color))
        self.trim_set_out_button.setIconSize(icon_size)
        self.trim_set_out_button.setToolTip("Set out-point at the current position")
        self.trim_set_out_button.setEnabled(False)
        self.trim_out_edit = TimecodeEdit()
        self.trim_out_edit.setFixedWidth(84)
        self.trim_out_edit.setToolTip(
            "Out-point (H:MM:SS:FF) - drag to nudge, click to type"
        )
        self.trim_out_edit.setEnabled(False)

        self.trim_timecode_label = self.trim_transport.time_label
        tc_font = self.trim_timecode_label.font()
        if tc_font.pointSize() > 0:
            tc_font.setPointSize(max(7, tc_font.pointSize() - 2))
        self.trim_timecode_label.setFont(tc_font)
        self.trim_timecode_label.setStyleSheet("color: gray;")

        self.trim_reset_button = QPushButton("Reset")
        self.trim_reset_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton)
        )
        self.trim_reset_button.setIconSize(icon_size)
        self.trim_reset_button.setEnabled(False)

        timecode_divider = QFrame()
        timecode_divider.setFrameShape(QFrame.VLine)
        timecode_divider.setFrameShadow(QFrame.Plain)
        timecode_divider.setStyleSheet(f"color: {DIVIDER_COLOR};")

        reset_divider = QFrame()
        reset_divider.setFrameShape(QFrame.VLine)
        reset_divider.setFrameShadow(QFrame.Plain)
        reset_divider.setStyleSheet(f"color: {DIVIDER_COLOR};")

        # All the transport/trim controls, grouped together as one cluster
        # centered under the (now full-width) scrubber above: play, then
        # in-point controls, then out-point controls (mirrored), then a
        # divider, the scrubber timecode, another divider, and reset.
        controls_row = QHBoxLayout()
        controls_row.addStretch(1)
        controls_row.addWidget(self.trim_play_button, alignment=Qt.AlignVCenter)
        controls_row.addSpacing(12)
        controls_row.addWidget(self.trim_goto_in_button, alignment=Qt.AlignVCenter)
        controls_row.addSpacing(4)
        controls_row.addWidget(self.trim_set_in_button, alignment=Qt.AlignVCenter)
        controls_row.addSpacing(4)
        controls_row.addWidget(self.trim_in_edit, alignment=Qt.AlignVCenter)
        controls_row.addSpacing(20)
        controls_row.addWidget(self.trim_out_edit, alignment=Qt.AlignVCenter)
        controls_row.addSpacing(4)
        controls_row.addWidget(self.trim_set_out_button, alignment=Qt.AlignVCenter)
        controls_row.addSpacing(4)
        controls_row.addWidget(self.trim_goto_out_button, alignment=Qt.AlignVCenter)
        controls_row.addSpacing(12)
        controls_row.addWidget(timecode_divider)
        controls_row.addSpacing(12)
        controls_row.addWidget(self.trim_timecode_label, alignment=Qt.AlignVCenter)
        controls_row.addSpacing(12)
        controls_row.addWidget(reset_divider)
        controls_row.addSpacing(12)
        controls_row.addWidget(self.trim_reset_button, alignment=Qt.AlignVCenter)
        controls_row.addStretch(1)
        preview_layout.addLayout(controls_row)

        self.trim_range_label = QLabel("Full clip selected")
        self.trim_range_label.setStyleSheet("color: gray;")
        self.trim_range_label.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self.trim_range_label)

        page_layout.addWidget(preview_group, stretch=1)

        self.trim_range.rangeChanged.connect(self._on_trim_range_changed)
        self.trim_reset_button.clicked.connect(self._on_trim_reset_clicked)
        self.trim_set_in_button.clicked.connect(self._on_trim_set_in_clicked)
        self.trim_set_out_button.clicked.connect(self._on_trim_set_out_clicked)
        self.trim_goto_in_button.clicked.connect(self._on_trim_goto_in_clicked)
        self.trim_goto_out_button.clicked.connect(self._on_trim_goto_out_clicked)
        self.trim_in_edit.framesChanged.connect(self._on_trim_in_frames_changed)
        self.trim_out_edit.framesChanged.connect(self._on_trim_out_frames_changed)
        # Play/pause, scrubbing, and the elapsed/duration label are wired up
        # internally by trim_transport (VideoTransport) already.

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_source(self, info: probe.MediaInfo | None, enabled: bool):
        """Point the preview player at `info` (or clear it) and reset the
        trim selection to the full clip. `enabled` decides whether the
        transport/in-out controls are usable - the caller works this out
        (has a video stream, and isn't in a mode where trim doesn't apply,
        e.g. batch) since this panel has no notion of "mode" itself."""
        self._source_info = info
        self._trim_range = None
        self.trim_range.set_range(0.0, 1.0, emit=False)
        self._update_trim_range_label()
        self.trim_position_slider.set_trim_range(0.0, 1.0)
        self._sync_trim_edits()

        self.trim_play_button.setEnabled(enabled)
        self.trim_set_in_button.setEnabled(enabled)
        self.trim_set_out_button.setEnabled(enabled)
        self.trim_goto_in_button.setEnabled(enabled)
        self.trim_goto_out_button.setEnabled(enabled)
        self.trim_in_edit.setEnabled(enabled)
        self.trim_out_edit.setEnabled(enabled)
        self.trim_position_slider.setEnabled(enabled)

        if enabled:
            self.trim_scene.setSceneRect(0, 0, info.video.width, info.video.height)
            self.trim_video_item.setSize(QSizeF(info.video.width, info.video.height))
            self.trim_crop_mask.set_bounds(info.video.width, info.video.height)
            self.trim_player.setSource(QUrl.fromLocalFile(info.path))
            # Crop mirroring is the caller's job: it should follow this with
            # a set_crop() call using whatever crop is currently active,
            # exactly like the original inline implementation did with the
            # (always live, never stale) crop_rect at the moment it ran.
        else:
            self.trim_player.setSource(QUrl())
            self.trim_position_slider.setRange(0, 0)
            self.trim_timecode_label.setText("00:00 / 00:00")

    def set_crop(self, crop_rect: QRect | None):
        """Mirror the Size/Crop page's crop selection in the preview - the
        video item itself always stays at full size (QGraphicsVideoItem has
        no native crop support), so this masks out the discarded area and
        zooms the view to the kept region, matching what the export will
        actually produce instead of always showing the full frame. Works
        against whatever set_source() was last given, independent of
        whether the controls are currently enabled - a crop edited while
        e.g. in batch mode should still update this."""
        self._update_trim_crop_view(crop_rect)

    def trim_range_seconds(self) -> tuple[float, float] | None:
        """(start_s, end_s) if a non-full-clip range is selected, else
        None - what command building should treat as "no trim"."""
        return self._trim_range

    def stop_playback(self):
        self.trim_transport.stop()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _update_trim_crop_view(self, crop_rect: QRect | None):
        info = self._source_info
        if not (info and info.video):
            return
        source_w, source_h = info.video.width, info.video.height
        if crop_rect is not None:
            x = min(crop_rect.x(), source_w - 1)
            y = min(crop_rect.y(), source_h - 1)
            w = min(crop_rect.width(), source_w - x)
            h = min(crop_rect.height(), source_h - y)
            self.trim_crop_mask.set_crop(x, y, w, h)
            self.trim_view.set_focus_rect(QRectF(x, y, w, h))
        else:
            self.trim_crop_mask.set_crop(0, 0, source_w, source_h)
            self.trim_view.set_focus_rect(None)

    def _update_trim_range_label(self):
        if self._trim_range is None:
            self.trim_range_label.setText("Full clip selected")
            self.trim_reset_button.setEnabled(False)
            return
        start, end = self._trim_range
        self.trim_range_label.setText(
            f"Trimmed to {probe.human_duration(start)}–{probe.human_duration(end)}"
            f" ({probe.human_duration(end - start)} kept)"
        )
        self.trim_reset_button.setEnabled(True)

    def _on_trim_range_changed(self, start_frac: float, end_frac: float):
        """The single handler for every way the trim selection can change
        (Set In/Out, typed field, Reset) - self.trim_range is the one source
        of truth, this just fans its rangeChanged signal out to everything
        that displays it."""
        info = self._source_info
        duration = info.duration_s if info else 0.0
        if duration <= 0:
            return
        # Snap back to "no trim" once the range covers the full extremes,
        # rather than leaving a no-op trim sitting around that just
        # reproduces the source unchanged.
        if start_frac <= 0.0005 and end_frac >= 0.9995:
            self._trim_range = None
        else:
            self._trim_range = (start_frac * duration, end_frac * duration)
        self._update_trim_range_label()
        self.trim_position_slider.set_trim_range(start_frac, end_frac)
        self._sync_trim_edits()
        self.settingsChanged.emit()

    def _on_trim_reset_clicked(self):
        self.trim_range.set_range(0.0, 1.0)

    def _set_trim_bound_from_playhead(self, which: str):
        """Move the in- or out-point to the scrubber's current position.
        Routed through trim_range.set_range() (rather than setting
        self._trim_range directly) so the range label, slider mask and
        fields all update the exact same way a typed edit would."""
        info = self._source_info
        duration = info.duration_s if info else 0.0
        if duration <= 0:
            return
        frac = max(0.0, min(1.0, (self.trim_player.position() / 1000.0) / duration))
        if which == "start":
            self.trim_range.set_range(min(frac, self.trim_range.end() - MIN_GAP), self.trim_range.end())
        else:
            self.trim_range.set_range(self.trim_range.start(), max(frac, self.trim_range.start() + MIN_GAP))

    def _on_trim_set_in_clicked(self):
        self._set_trim_bound_from_playhead("start")

    def _on_trim_set_out_clicked(self):
        self._set_trim_bound_from_playhead("end")

    def _seek_trim_player_to(self, frac: float):
        info = self._source_info
        duration = info.duration_s if info else 0.0
        if duration <= 0:
            return
        self.trim_player.setPosition(int(frac * duration * 1000))

    def _on_trim_goto_in_clicked(self):
        self._seek_trim_player_to(self.trim_range.start())

    def _on_trim_goto_out_clicked(self):
        self._seek_trim_player_to(self.trim_range.end())

    def _current_trim_fps(self) -> float:
        info = self._source_info
        return info.video.fps if (info and info.video and info.video.fps > 0) else 25.0

    def _sync_trim_edits(self):
        info = self._source_info
        duration = info.duration_s if info else 0.0
        fps = self._current_trim_fps()
        self.trim_in_edit.set_fps(fps)
        self.trim_out_edit.set_fps(fps)
        self.trim_in_edit.set_frames(self.trim_range.start() * duration * fps, emit=False)
        self.trim_out_edit.set_frames(self.trim_range.end() * duration * fps, emit=False)

    def _apply_trim_frames(self, frames: int, which: str):
        """Handles both a dragged and a typed-and-committed change from
        either TimecodeEdit - both surface as the same framesChanged signal,
        so there's no need to distinguish them here."""
        info = self._source_info
        duration = info.duration_s if info else 0.0
        fps = self._current_trim_fps()
        if duration <= 0:
            return
        frac = max(0.0, min(1.0, (frames / fps) / duration))
        if which == "start":
            self.trim_range.set_range(min(frac, self.trim_range.end() - MIN_GAP), self.trim_range.end())
        else:
            self.trim_range.set_range(self.trim_range.start(), max(frac, self.trim_range.start() + MIN_GAP))

    def _on_trim_in_frames_changed(self, frames: int):
        self._apply_trim_frames(frames, "start")

    def _on_trim_out_frames_changed(self, frames: int):
        self._apply_trim_frames(frames, "end")
