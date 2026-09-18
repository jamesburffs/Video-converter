"""Trim-selection state and the scrubber widget that visualizes it.

TrimRange holds the current trim selection as fractions of the clip's total
duration (0.0-1.0) - it doesn't know about seconds at all, or about how the
selection gets edited (drag, buttons, typed values); it's just the one
source of truth that the scrubber's mask, the in/out text fields, and
command building all read from and write to.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLineEdit

from .widgets import NoWheelSlider

MIN_GAP = 0.005  # smallest allowed distance between start/end, as a fraction


class TrimRange(QObject):
    rangeChanged = Signal(float, float)  # start_fraction, end_fraction

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start = 0.0
        self._end = 1.0

    def set_range(self, start: float, end: float, emit: bool = True):
        start = max(0.0, min(1.0, start))
        end = max(0.0, min(1.0, end))
        if end < start:
            start, end = end, start
        changed = (start, end) != (self._start, self._end)
        self._start, self._end = start, end
        if emit and changed:
            self.rangeChanged.emit(self._start, self._end)

    def start(self) -> float:
        return self._start

    def end(self) -> float:
        return self._end


class TrimScrubberSlider(NoWheelSlider):
    """The playback scrubber, which also masks out the portions outside the
    current trim range directly on top of its own groove/handle - a solid
    dimming overlay with a crisp edge at each cut point, rather than a
    gradient background-color trick (tried first; it read as a soft blend
    rather than a clear "this part is gone" indicator). Ignoring the mouse
    wheel (inherited from NoWheelSlider, like the rest of the app's
    sliders) keeps scrolling the settings panel from accidentally seeking."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._start = 0.0
        self._end = 1.0

    def set_trim_range(self, start: float, end: float):
        self._start, self._end = start, end
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._start <= 0.0005 and self._end >= 0.9995:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        w, h = self.width(), self.height()
        start_x = self._start * w
        end_x = self._end * w

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(70, 70, 70, 160))
        if start_x > 0:
            painter.drawRect(QRectF(0, 0, start_x, h))
        if end_x < w:
            painter.drawRect(QRectF(end_x, 0, w - end_x, h))

        pen = QPen(QColor(255, 255, 255, 230))
        pen.setWidth(1)
        painter.setPen(pen)
        if start_x > 0:
            painter.drawLine(QPointF(start_x, 0), QPointF(start_x, h))
        if end_x < w:
            painter.drawLine(QPointF(end_x, 0), QPointF(end_x, h))


def _parse_frame_timecode(text: str, fps: float) -> float | None:
    """Parse "FF", "SS:FF", "MM:SS:FF" or "H:MM:SS:FF" into seconds - the
    last colon-separated component is always frames (divided by fps), the
    rest fold as hours/minutes/seconds the usual base-60 way."""
    fps = fps if fps and fps > 0 else 25.0
    parts = text.strip().split(":")
    if not parts or len(parts) > 4:
        return None
    try:
        values = [float(p) for p in parts]
    except ValueError:
        return None
    frames_part = values[-1]
    seconds = 0.0
    for v in values[:-1]:
        seconds = seconds * 60 + v
    seconds += frames_part / fps
    return seconds if seconds >= 0 else None


class TimecodeEdit(QLineEdit):
    """A small text field showing a frame-accurate H:MM:SS:FF timecode,
    which can also be click-dragged left/right to nudge the value - like a
    numeric drag field (Blender/Photoshop-style) rather than a plain text
    box. A plain click (no real movement) instead focuses the field and
    selects all its text, ready to type a replacement.

    Purely frame-count based and has no idea what it represents (an in- or
    out-point, a fraction of some duration, etc) - the caller converts
    to/from that meaning via fps/duration and listens for framesChanged.
    """

    framesChanged = Signal(int)  # emitted for both a drag and a typed commit

    _DRAG_THRESHOLD_PX = 4
    _PIXELS_PER_FRAME = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fps = 25.0
        self._frames = 0
        self._press_pos: QPointF | None = None
        self._press_frames = 0
        self._dragging = False
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.SizeHorCursor)
        self._refresh_text()
        self.editingFinished.connect(self._on_editing_finished)

    def set_fps(self, fps: float):
        self._fps = fps if fps and fps > 0 else 25.0

    def set_frames(self, frames: int, emit: bool = True):
        frames = max(0, int(round(frames)))
        changed = frames != self._frames
        self._frames = frames
        self._refresh_text()
        if emit and changed:
            self.framesChanged.emit(self._frames)

    def frames(self) -> int:
        return self._frames

    def _refresh_text(self):
        fps_i = max(1, int(round(self._fps)))
        total_seconds, fr = divmod(self._frames, fps_i)
        s = total_seconds % 60
        m = (total_seconds // 60) % 60
        h = total_seconds // 3600
        self.setText(f"{h:02d}:{m:02d}:{s:02d}:{fr:02d}")

    def _on_editing_finished(self):
        seconds = _parse_frame_timecode(self.text(), self._fps)
        if seconds is None:
            self._refresh_text()  # revert to the last valid value
            return
        self.set_frames(round(seconds * self._fps))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.position()
            self._press_frames = self._frames
            self._dragging = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press_pos is not None:
            dx = event.position().x() - self._press_pos.x()
            if not self._dragging and abs(dx) < self._DRAG_THRESHOLD_PX:
                return
            self._dragging = True
            self.set_frames(self._press_frames + int(dx / self._PIXELS_PER_FRAME))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._press_pos is not None:
            was_dragging = self._dragging
            self._press_pos = None
            self._dragging = False
            if not was_dragging:
                self.setFocus()
                self.selectAll()
            event.accept()
            return
        super().mouseReleaseEvent(event)
