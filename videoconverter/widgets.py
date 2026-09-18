"""Small reusable Qt widget subclasses with no dependencies on the rest of
the app - safe to import from any module (including ones that import each
other) without risking a circular import.
"""
from __future__ import annotations

from PySide6.QtWidgets import QSlider


class NoWheelSlider(QSlider):
    """A QSlider that ignores mouse wheel events, so scrolling a panel over
    it doesn't accidentally change the value."""

    def wheelEvent(self, event):
        event.ignore()
