"""A QMediaPlayer plus the play/pause button, scrubber and elapsed/duration
label that drive it, wired together once - CropDialog and the Trim page
both need this exact playback plumbing (nudge to the first frame once
media loads rather than showing a blank widget, keep the scrubber in sync
while it isn't being dragged, format the "elapsed / total" label) and used
to each carry their own separately-maintained copy of it.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QLabel, QPushButton, QSlider, QStyle

from .widgets import NoWheelSlider


def _format_ms(ms: int) -> str:
    s = max(0, ms) // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


class VideoTransport(QObject):
    """Not a QWidget - it doesn't impose any layout of its own. play_button,
    position_slider and time_label are public attributes for the caller to
    place into whatever layout it wants, since CropDialog (one row: text
    "Play"/"Pause" button, slider, label) and the Trim page (scrubber
    full-width above a separate controls row holding an icon-only play
    button and the label alongside other trim controls) lay them out
    completely differently.

    icon_button picks the play button's presentation: an icon (swapped
    between the standard play/pause glyphs, with the state as a tooltip)
    when True, or plain "Play"/"Pause" text when False. slider lets the
    caller supply a specialized scrubber (e.g. the Trim page's
    TrimScrubberSlider, which also paints the trim mask) in place of the
    plain default.
    """

    def __init__(
        self, video_output, icon_button: bool = False,
        slider: QSlider | None = None, parent=None,
    ):
        super().__init__(parent)
        self.player = QMediaPlayer(self)
        self.player.setVideoOutput(video_output)

        self._icon_button = icon_button
        self.play_button = QPushButton()
        if not icon_button:
            self.play_button.setText("Play")
        self._apply_play_button_state(playing=False)

        self.position_slider = slider if slider is not None else NoWheelSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)

        self.time_label = QLabel("00:00 / 00:00")

        self.play_button.clicked.connect(self._on_play_clicked)
        self.position_slider.sliderMoved.connect(self.player.setPosition)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)

    def set_source(self, url: QUrl):
        self.player.setSource(url)

    def stop(self):
        self.player.stop()

    # ------------------------------------------------------------------
    def _on_media_status_changed(self, status):
        # Nudge the player so a frame renders at the start position instead
        # of showing a blank widget before the user presses Play.
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            self.player.play()
            self.player.pause()

    def _on_play_clicked(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_playback_state_changed(self, state):
        self._apply_play_button_state(state == QMediaPlayer.PlaybackState.PlayingState)

    def _apply_play_button_state(self, playing: bool):
        if self._icon_button:
            icon = QStyle.SP_MediaPause if playing else QStyle.SP_MediaPlay
            self.play_button.setIcon(self.play_button.style().standardIcon(icon))
            self.play_button.setToolTip("Pause" if playing else "Play")
        else:
            self.play_button.setText("Pause" if playing else "Play")

    def _on_duration_changed(self, duration: int):
        self.position_slider.setRange(0, duration)
        self._update_time_label()

    def _on_position_changed(self, position: int):
        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(position)
        self._update_time_label()

    def _update_time_label(self):
        self.time_label.setText(
            f"{_format_ms(self.player.position())} / {_format_ms(self.player.duration())}"
        )
