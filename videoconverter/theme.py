"""A deliberately consistent look across platforms.

Left alone, Qt defaults to whatever style is native to wherever it's
running - Fusion only by accident on the Linux build (falling back to it
because no Breeze plugin was available to load), and macOS's own native
QMacStyle on the macOS build, with genuinely different widget metrics
(control sizes, spacing) that made the two builds' layouts feel
different, not just differently colored. Explicitly selecting Fusion (a
style built directly into Qt itself - no plugin loading, so none of the
transitive shared-library risk a real native style like Breeze carries in
a frozen build, see external_env.py) and layering a custom dark palette
and stylesheet on top gets the same, deliberately-designed look
everywhere instead.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

# Matches the app's own existing accent color (the Start Export button and
# the tab-bar accent line - see main_window/base.py) rather than
# introducing a second one.
ACCENT = "#51A2DA"
ACCENT_HOVER = "#6BB0E0"
ACCENT_PRESSED = "#3E86BD"
ACCENT_TEXT = "#232629"  # matches the Start Export button's own dark text

_WINDOW = "#2b2e33"
_BASE = "#232629"
_ALT_BASE = "#31363b"
_BUTTON = "#31363b"
_BUTTON_HOVER = "#3a3f45"
_TEXT = "#eff0f1"
_DISABLED_TEXT = "#6e7276"
_BORDER = "#43474c"


def _build_palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor(_WINDOW))
    p.setColor(QPalette.WindowText, QColor(_TEXT))
    p.setColor(QPalette.Base, QColor(_BASE))
    p.setColor(QPalette.AlternateBase, QColor(_ALT_BASE))
    p.setColor(QPalette.ToolTipBase, QColor(_ALT_BASE))
    p.setColor(QPalette.ToolTipText, QColor(_TEXT))
    p.setColor(QPalette.Text, QColor(_TEXT))
    p.setColor(QPalette.Button, QColor(_BUTTON))
    p.setColor(QPalette.ButtonText, QColor(_TEXT))
    p.setColor(QPalette.BrightText, QColor("#ff6b6b"))
    p.setColor(QPalette.Link, QColor(ACCENT))
    p.setColor(QPalette.Highlight, QColor(ACCENT))
    p.setColor(QPalette.HighlightedText, QColor(ACCENT_TEXT))
    p.setColor(QPalette.PlaceholderText, QColor(_DISABLED_TEXT))

    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(_DISABLED_TEXT))
    p.setColor(QPalette.Disabled, QPalette.Highlight, QColor(_ALT_BASE))
    p.setColor(QPalette.Disabled, QPalette.HighlightedText, QColor(_DISABLED_TEXT))
    return p


_STYLESHEET = f"""
QPushButton {{
    background-color: {_BUTTON};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    padding: 4px 10px;
}}
QPushButton:hover {{ background-color: {_BUTTON_HOVER}; }}
QPushButton:pressed {{ background-color: {_BASE}; }}
QPushButton:disabled {{ color: {_DISABLED_TEXT}; border-color: {_BASE}; }}
QPushButton:default {{ border: 1px solid {ACCENT}; }}

QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
    background-color: {_BASE};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 5px;
    padding: 3px 6px;
}}
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled {{
    color: {_DISABLED_TEXT};
}}
/* The drop-down/up-down-button sub-controls are deliberately left
   unstyled: Qt's stylesheet engine doesn't support the usual CSS
   zero-size-border triangle trick for a custom arrow glyph (it rendered
   as a solid block instead of a triangle), and Fusion's own built-in
   arrows already paint using the palette's colors natively - no QSS
   needed to make them fit the theme. */
QComboBox QAbstractItemView {{
    background-color: {_BASE};
    color: {_TEXT};
    selection-background-color: {ACCENT};
    selection-color: {ACCENT_TEXT};
    border: 1px solid {_BORDER};
    outline: none;
}}

QPlainTextEdit, QTableWidget, QListWidget {{
    background-color: {_BASE};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 5px;
}}
QHeaderView::section {{
    background-color: {_BUTTON};
    color: {_TEXT};
    border: none;
    border-bottom: 1px solid {_BORDER};
    padding: 4px;
}}
QTableWidget::item:selected, QListWidget::item:selected {{
    background-color: {ACCENT};
    color: {ACCENT_TEXT};
}}

QTabWidget::pane {{ border: 1px solid {_BORDER}; border-radius: 6px; top: -1px; }}
QTabBar::tab {{
    background-color: transparent;
    color: {_DISABLED_TEXT};
    padding: 6px 16px;
    border: none;
}}
QTabBar::tab:selected {{ color: {_TEXT}; }}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {_BORDER};
    background-color: {_BASE};
}}
QCheckBox::indicator {{ border-radius: 3px; }}
QRadioButton::indicator {{ border-radius: 7px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox:disabled, QRadioButton:disabled {{ color: {_DISABLED_TEXT}; }}

QSlider::groove:horizontal {{
    height: 4px;
    background: {_BORDER};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    margin: -6px 0;
    background: {_TEXT};
    border-radius: 7px;
}}
QSlider::handle:horizontal:disabled {{ background: {_DISABLED_TEXT}; }}

QProgressBar {{
    background-color: {_BASE};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    text-align: center;
    color: {_TEXT};
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 5px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 12px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {_BORDER};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {_DISABLED_TEXT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QScrollBar:horizontal {{
    background: transparent;
    height: 12px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {_BORDER};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {_DISABLED_TEXT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

QMenuBar {{ background-color: {_WINDOW}; color: {_TEXT}; }}
QMenuBar::item:selected {{ background-color: {_BUTTON_HOVER}; }}
QMenu {{
    background-color: {_ALT_BASE};
    color: {_TEXT};
    border: 1px solid {_BORDER};
}}
QMenu::item:selected {{ background-color: {ACCENT}; color: {ACCENT_TEXT}; }}

QToolTip {{
    background-color: {_ALT_BASE};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    padding: 4px;
}}
"""


def apply_theme(app: QApplication) -> None:
    """Call once, right after constructing the QApplication and before
    building any windows, so every widget picks up the style/palette/
    stylesheet from the moment it's first shown."""
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setPalette(_build_palette())
    app.setStyleSheet(_STYLESHEET)
