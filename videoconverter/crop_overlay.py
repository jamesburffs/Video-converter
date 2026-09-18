"""A QGraphicsItem that draws a draggable crop-selection rectangle directly
in the video's own pixel coordinate space.

It's added to the same QGraphicsScene as a QGraphicsVideoItem (rather than
being a QWidget overlaid on a QVideoWidget) so both are composited together
in one paint pass. A plain QWidget sibling doesn't reliably work here: on
Linux, QVideoWidget commonly renders through a hardware-accelerated surface
that paints outside Qt's normal widget backing store, so once real frames
start flowing a translucent overlay widget can end up silently painted over.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject

MIN_CROP = 8  # smallest crop width/height, in source video pixels

# Order matches the points _handle_centers() yields (row-major, skipping
# the untouched center).
_HANDLE_NAMES = ["tl", "t", "tr", "l", "r", "bl", "b", "br"]


def draw_crop_mask(painter: QPainter, full: QRectF, crop: QRectF, color: QColor) -> None:
    """Fill the four rectangles of `full` outside `crop` (above, below,
    left, right) with a flat `color` - the shared masking geometry behind
    CropOverlayItem's translucent dimming, CropMaskItem's opaque cover, and
    MainWindow's own static crop preview, which differ only in color/alpha
    and in whether it's paired with drag handles."""
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    painter.drawRect(QRectF(full.left(), full.top(), full.width(), crop.top() - full.top()))
    painter.drawRect(QRectF(full.left(), crop.bottom(), full.width(), full.bottom() - crop.bottom()))
    painter.drawRect(QRectF(full.left(), crop.top(), crop.left() - full.left(), crop.height()))
    painter.drawRect(QRectF(crop.right(), crop.top(), full.right() - crop.right(), crop.height()))


class CropOverlayItem(QGraphicsObject):
    cropChanged = Signal(int, int, int, int)  # x, y, w, h - video pixel coords

    def __init__(self, video_w: int, video_h: int, parent=None):
        super().__init__(parent)
        self._video_w = max(1, video_w)
        self._video_h = max(1, video_h)
        self._crop = QRectF(0, 0, self._video_w, self._video_h)
        self._handle_size = max(10.0, min(self._video_w, self._video_h) * 0.02)
        self._drag_mode: str | None = None
        self._drag_start_pos = QPointF()
        self._drag_start_crop = QRectF()
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setZValue(1)  # above the video item

    # ------------------------------------------------------------------
    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._video_w, self._video_h)

    def set_crop(self, x: float, y: float, w: float, h: float):
        self._crop = self._clamped(QRectF(x, y, w, h))
        self.update()

    def crop_rect(self) -> QRect:
        r = self._crop
        return QRect(int(round(r.x())), int(round(r.y())), int(round(r.width())), int(round(r.height())))

    def _clamped(self, r: QRectF) -> QRectF:
        x = max(0.0, min(r.x(), self._video_w - MIN_CROP))
        y = max(0.0, min(r.y(), self._video_h - MIN_CROP))
        w = max(float(MIN_CROP), min(r.width(), self._video_w - x))
        h = max(float(MIN_CROP), min(r.height(), self._video_h - y))
        return QRectF(x, y, w, h)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def _handle_centers(self):
        r = self._crop
        xs = [r.left(), r.center().x(), r.right()]
        ys = [r.top(), r.center().y(), r.bottom()]
        pts = []
        for y in ys:
            for x in xs:
                if x == r.center().x() and y == r.center().y():
                    continue
                pts.append(QPointF(x, y))
        return pts

    def paint(self, painter: QPainter, option, widget=None):
        full = self.boundingRect()
        r = self._crop

        draw_crop_mask(painter, full, r, QColor(0, 0, 0, 140))

        pen = QPen(QColor(255, 255, 255))
        pen.setWidthF(max(1.0, min(self._video_w, self._video_h) * 0.002))
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(r)

        hs = self._handle_size
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        for c in self._handle_centers():
            painter.drawRect(QRectF(c.x() - hs / 2, c.y() - hs / 2, hs, hs))

    # ------------------------------------------------------------------
    # Mouse interaction - event.pos() arrives pre-mapped into this item's
    # own coordinate system, i.e. already in video pixel space.
    # ------------------------------------------------------------------
    def _handle_at(self, pos: QPointF) -> str | None:
        hs = self._handle_size
        for name, c in zip(_HANDLE_NAMES, self._handle_centers()):
            if abs(pos.x() - c.x()) <= hs and abs(pos.y() - c.y()) <= hs:
                return name
        return None

    def mousePressEvent(self, event):
        pos = event.pos()
        handle = self._handle_at(pos)
        self._drag_start_pos = pos
        if handle:
            self._drag_mode = handle
            self._drag_start_crop = QRectF(self._crop)
        elif self._crop.contains(pos):
            self._drag_mode = "move"
            self._drag_start_crop = QRectF(self._crop)
        else:
            self._drag_mode = "new"
            self._drag_start_crop = QRectF(pos, pos)
        event.accept()

    def mouseMoveEvent(self, event):
        if not self._drag_mode:
            return
        pos = event.pos()
        dx = pos.x() - self._drag_start_pos.x()
        dy = pos.y() - self._drag_start_pos.y()
        start = self._drag_start_crop

        if self._drag_mode == "move":
            r = QRectF(start)
            r.moveLeft(start.left() + dx)
            r.moveTop(start.top() + dy)
        elif self._drag_mode == "new":
            x0, y0 = start.left(), start.top()
            x1, y1 = pos.x(), pos.y()
            r = QRectF(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
        else:
            left, top, right, bottom = start.left(), start.top(), start.right(), start.bottom()
            if "l" in self._drag_mode:
                left = start.left() + dx
            if "r" in self._drag_mode:
                right = start.right() + dx
            if "t" in self._drag_mode:
                top = start.top() + dy
            if "b" in self._drag_mode:
                bottom = start.bottom() + dy
            if right <= left:
                right = left + 1
            if bottom <= top:
                bottom = top + 1
            r = QRectF(QPointF(left, top), QPointF(right, bottom))

        self._crop = self._clamped(r)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_mode:
            r = self.crop_rect()
            self.cropChanged.emit(r.x(), r.y(), r.width(), r.height())
        self._drag_mode = None
        event.accept()


class CropMaskItem(QGraphicsItem):
    """A static, non-interactive opaque mask covering everything in a
    video_w x video_h scene outside a given crop rect. Used to make a live
    video preview (e.g. the Trim page's playback) appear cropped without
    actually re-rendering the frame - QGraphicsVideoItem has no native crop
    support, so the video item is left at its full size and this just
    paints over the discarded area on top of it. Shares its masking
    geometry with CropOverlayItem's own dimming (see draw_crop_mask),
    just opaque instead of translucent and without any drag handling."""

    def __init__(self, video_w: int, video_h: int, parent=None):
        super().__init__(parent)
        self._video_w = max(1, video_w)
        self._video_h = max(1, video_h)
        self._crop = QRectF(0, 0, self._video_w, self._video_h)
        self.setZValue(1)  # above the video item

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._video_w, self._video_h)

    def set_bounds(self, video_w: int, video_h: int):
        """Resize the full (uncropped) frame this mask is drawn against -
        needed since the item is created before any file is loaded, when
        the real dimensions aren't known yet."""
        self.prepareGeometryChange()
        self._video_w = max(1, video_w)
        self._video_h = max(1, video_h)
        self._crop = QRectF(0, 0, self._video_w, self._video_h)

    def set_crop(self, x: float, y: float, w: float, h: float):
        self.prepareGeometryChange()
        self._crop = QRectF(x, y, w, h)
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        full = self.boundingRect()
        r = self._crop
        if r == full:
            return
        # Matches the preview scene's own background.
        draw_crop_mask(painter, full, r, QColor(20, 20, 20))
