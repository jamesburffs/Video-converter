"""Custom-drawn QIcons for controls where the built-in Qt standard icons
either don't exist or would send the wrong signal (see each function's
docstring for why). Pure functions with no Qt widget/window dependencies -
each takes a color and returns a QIcon, so they're independently reusable
and testable without constructing any part of the app's UI.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF


def trim_bound_icon(direction: str, color: QColor) -> QIcon:
    """A vertical bar with a single arrowhead pointing at it - deliberately
    not Qt's SP_MediaSkipBackward/Forward, whose double-chevron look is
    conventionally read as "jump to start/end", not "mark an in/out point".

    direction "start": bar on the left, arrow to its right pointing left
    (into the bar). direction "end": bar on the right, arrow to its left
    pointing right (into the bar).
    """
    size = 20
    margin = 3.0
    bar_w = 2.4
    gap = 2.0
    half_h = 5.0
    mid = size / 2.0

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)

    if direction == "start":
        bar_x = margin
        painter.drawRect(QRectF(bar_x, margin, bar_w, size - 2 * margin))
        tip_x = bar_x + bar_w + gap
        base_x = size - margin
        arrow = QPolygonF([
            QPointF(tip_x, mid),
            QPointF(base_x, mid - half_h),
            QPointF(base_x, mid + half_h),
        ])
    else:
        bar_x = size - margin - bar_w
        painter.drawRect(QRectF(bar_x, margin, bar_w, size - 2 * margin))
        tip_x = bar_x - gap
        base_x = margin
        arrow = QPolygonF([
            QPointF(tip_x, mid),
            QPointF(base_x, mid - half_h),
            QPointF(base_x, mid + half_h),
        ])
    painter.drawPolygon(arrow)
    painter.end()
    return QIcon(pixmap)


def trim_goto_icon(direction: str, color: QColor) -> QIcon:
    """A corner bracket with a real (open, two-stroke) arrowhead pointing
    into it - visually distinct from trim_bound_icon's solid bar + filled
    triangle, so "jump the playhead to this mark" doesn't look like "set
    this mark". direction "start": bracket open to the right, on the left
    of the icon. direction "end": bracket open to the left, on the right.
    """
    size = 20
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    pen = QPen(color)
    pen.setWidthF(1.8)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)

    top_y, bottom_y = 4.0, size - 4.0
    mid = size / 2.0
    tick = 3.5
    head = 3.0

    if direction == "start":
        bracket_x = 4.5
        painter.drawLine(QPointF(bracket_x, top_y), QPointF(bracket_x, bottom_y))
        painter.drawLine(QPointF(bracket_x, top_y), QPointF(bracket_x + tick, top_y))
        painter.drawLine(QPointF(bracket_x, bottom_y), QPointF(bracket_x + tick, bottom_y))
        shaft_from = size - 4.0
        shaft_to = bracket_x + tick + 3.0
        painter.drawLine(QPointF(shaft_from, mid), QPointF(shaft_to, mid))
        painter.drawLine(QPointF(shaft_to, mid), QPointF(shaft_to + head, mid - head))
        painter.drawLine(QPointF(shaft_to, mid), QPointF(shaft_to + head, mid + head))
    else:
        bracket_x = size - 4.5
        painter.drawLine(QPointF(bracket_x, top_y), QPointF(bracket_x, bottom_y))
        painter.drawLine(QPointF(bracket_x, top_y), QPointF(bracket_x - tick, top_y))
        painter.drawLine(QPointF(bracket_x, bottom_y), QPointF(bracket_x - tick, bottom_y))
        shaft_from = 4.0
        shaft_to = bracket_x - tick - 3.0
        painter.drawLine(QPointF(shaft_from, mid), QPointF(shaft_to, mid))
        painter.drawLine(QPointF(shaft_to, mid), QPointF(shaft_to - head, mid - head))
        painter.drawLine(QPointF(shaft_to, mid), QPointF(shaft_to - head, mid + head))

    painter.end()
    return QIcon(pixmap)


def export_icon(color: QColor) -> QIcon:
    """A simple filled play triangle for the export/convert button - tried
    recoloring the standard save icon first (fill wherever it has alpha),
    but that icon's shading isn't done with transparency, so it came out as
    a solid, unreadable block. A plain triangle reads clearly at button
    size and matches "Start Export" ("start" being the operative word)."""
    size = 20
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    triangle = QPolygonF([
        QPointF(4.5, 3.0),
        QPointF(4.5, size - 3.0),
        QPointF(size - 3.5, size / 2.0),
    ])
    painter.drawPolygon(triangle)
    painter.end()
    return QIcon(pixmap)
