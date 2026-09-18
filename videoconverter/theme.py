"""A consistent look across platforms: Fusion (a style built directly
into Qt itself - no plugin loading, so none of the transitive shared-
library risk a real native style like KDE's Breeze carries in a frozen
build, see external_env.py), with a hard-coded palette on top so every
user sees the same colors regardless of what theme (or lack of one) their
own system has installed - rather than either Fusion's own generic
default, or whatever a platform-theme integration plugin happens to
report (which is what made the un-styled Fusion build look reasonably
close to this app's usual dark look on a KDE system specifically, but
wouldn't be true on a system without one).

These exact values were pulled from a real, live KDE session's resolved
QPalette (a Nord-based color scheme) - see the conversation this came out
of - not invented from scratch, so this should look like a faithful
snapshot of that, not a new design. Deliberately palette-only: no QSS on
top (rounded corners, custom arrows, etc. were tried and reverted - see
git history on this file - in favor of plain Fusion's own widget shapes).
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

_ACTIVE = {
    QPalette.Window: "#2e3440",
    QPalette.WindowText: "#d8dee9",
    QPalette.Base: "#3b4252",
    QPalette.AlternateBase: "#2e3440",
    QPalette.Text: "#d8dee9",
    QPalette.Button: "#3c4454",
    QPalette.ButtonText: "#d8dee9",
    QPalette.BrightText: "#ffffff",
    QPalette.Link: "#5e81ac",
    QPalette.LinkVisited: "#7cb7ff",
    QPalette.Highlight: "#4c566a",
    QPalette.HighlightedText: "#d8dee9",
    QPalette.ToolTipBase: "#353945",
    QPalette.ToolTipText: "#d3dae3",
    QPalette.PlaceholderText: "#666a73",
}

_DISABLED = {
    QPalette.Window: "#2c323d",
    QPalette.WindowText: "#656a75",
    QPalette.Base: "#383f4e",
    QPalette.AlternateBase: "#2c323d",
    QPalette.Text: "#6d7381",
    QPalette.Button: "#394150",
    QPalette.ButtonText: "#6d7482",
    QPalette.BrightText: "#ffffff",
    QPalette.Link: "#44546c",
    QPalette.LinkVisited: "#4e6688",
    QPalette.Highlight: "#2c323d",
    QPalette.HighlightedText: "#656a75",
    QPalette.ToolTipBase: "#353945",
    QPalette.ToolTipText: "#d3dae3",
    QPalette.PlaceholderText: "#474c59",
}


# A plain (non-sunken/raised) QFrame divider line - QFrame.VLine/HLine
# with QFrame.Plain shadow - paints using the WindowText role by default,
# which makes sense for a frame drawn as part of a widget's own content
# but reads as too bright/prominent for a divider specifically once
# WindowText is a light color for body text (see _ACTIVE above). Divider
# QFrames should set their own styleSheet to this instead of relying on
# the palette. Matches the original Breeze theme's own divider color.
DIVIDER_COLOR = "#5A6170"


def _build_palette() -> QPalette:
    p = QPalette()
    for role, hex_color in _ACTIVE.items():
        p.setColor(QPalette.Active, role, QColor(hex_color))
        p.setColor(QPalette.Inactive, role, QColor(hex_color))
    for role, hex_color in _DISABLED.items():
        p.setColor(QPalette.Disabled, role, QColor(hex_color))
    return p


def apply_theme(app: QApplication) -> None:
    """Call once, right after constructing the QApplication and before
    building any windows."""
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setPalette(_build_palette())
