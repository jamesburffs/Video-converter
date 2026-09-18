"""The 'About VidKonverter' dialog, reachable from Help -> About VidKonverter."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ._version import __version__

ICONS_DIR = os.path.join(os.path.dirname(__file__), "icons")
# The dialog is shipped inside the videoconverter/ package, one level below
# the project root where LICENSE lives - this resolves correctly whether
# running from source or from a PyInstaller build, since packaging/build.py
# bundles LICENSE alongside the icons (see video_converter.spec).
LICENSE_PATH = os.path.join(os.path.dirname(__file__), "LICENSE")
LICENSE_URL = "https://www.gnu.org/licenses/gpl-3.0.txt"


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About VidKonverter")

        layout = QVBoxLayout(self)
        # setFixedWidth() alone (tried first) wasn't enough to stop the
        # word-wrapped labels below from occasionally getting clipped a
        # line short: their height is computed via heightForWidth() at
        # layout time, and a plain fixed *widget* width doesn't guarantee
        # that's already settled by the time that first happens. A
        # zero-height spacer that's just wide enough to force the whole
        # layout's minimum width does - the real width is then known
        # before any label's height is computed at all - and
        # SetFixedSize keeps the dialog locked to exactly whatever height
        # that content actually needs, recalculated live, rather than a
        # size that was only ever correct (or not) at construction time.
        width_spacer = QWidget()
        width_spacer.setFixedSize(420, 0)
        layout.addWidget(width_spacer)
        layout.setSizeConstraint(QVBoxLayout.SetFixedSize)

        header_row = QHBoxLayout()
        icon_label = QLabel()
        # Fixed, not left to the label's own sizeHint - a QLabel showing a
        # pixmap without setScaledContents doesn't stretch it to fill a
        # larger box, but it will still let the box (and so the visible
        # pixmap) come out shorter than this if the surrounding layout
        # ever has reason to allocate less, which read as the icon being
        # clipped top and bottom.
        icon_label.setFixedSize(72, 72)
        icon_label.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(os.path.join(ICONS_DIR, "vidkonverter-app-icon.png"))
        if not pixmap.isNull():
            icon_label.setPixmap(
                pixmap.scaled(
                    72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        header_row.addWidget(icon_label)
        # Top-align explicitly - the default is to center each item across
        # the row's full height, which (with the icon setting that height
        # to 72px against title_col's much shorter ~40px of actual
        # content) pushed "Version ..." down away from the icon's own top
        # edge and toward the description paragraph below instead. An
        # addStretch(1) at the end of title_col looks like the obvious fix
        # but isn't: nested inside a QHBoxLayout item like this, it makes
        # the row's own height balloon well past 72px rather than just
        # padding out title_col's slice of a fixed-height row.
        header_row.setAlignment(icon_label, Qt.AlignTop)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        # A small nudge down from dead-top - top-aligned with the icon's
        # own top edge read as sitting slightly high against it.
        title_col.setContentsMargins(0, 10, 0, 0)
        name_label = QLabel("VidKonverter")
        name_font = name_label.font()
        name_font.setPointSize(name_font.pointSize() + 4)
        name_font.setBold(True)
        name_label.setFont(name_font)
        title_col.addWidget(name_label)
        version_label = QLabel(f"Version {__version__}")
        version_label.setStyleSheet("color: gray;")
        title_col.addWidget(version_label)
        header_row.addLayout(title_col, stretch=1)
        header_row.setAlignment(title_col, Qt.AlignTop)
        layout.addLayout(header_row)
        layout.addSpacing(8)

        desc_label = QLabel(
            "A desktop GUI for converting and batch-converting video files "
            "with ffmpeg - container/codec selection, resolution and crop, "
            "trim, and alpha channel handling."
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        authors_label = QLabel("Written by James Burrows, with Claude (Anthropic).")
        authors_label.setWordWrap(True)
        layout.addWidget(authors_label)

        copyright_label = QLabel("Copyright © 2026 James Burrows")
        layout.addWidget(copyright_label)

        license_label = QLabel(
            "Licensed under the GNU General Public License v3.0. This "
            "program comes with ABSOLUTELY NO WARRANTY."
        )
        license_label.setWordWrap(True)
        license_label.setStyleSheet("color: gray;")
        layout.addWidget(license_label)

        ffmpeg_label = QLabel(
            "Uses ffmpeg (ffmpeg.org) - a separate program this app invokes "
            "at runtime, not bundled or modified."
        )
        ffmpeg_label.setWordWrap(True)
        ffmpeg_label.setStyleSheet("color: gray;")
        layout.addWidget(ffmpeg_label)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.view_license_button = QPushButton("View License")
        self.view_license_button.clicked.connect(self._on_view_license)
        button_row.addWidget(self.view_license_button)
        close_button = QPushButton("Close")
        close_button.setDefault(True)
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

    def _on_view_license(self):
        # Falls back to the canonical text online if this isn't running
        # from a checkout/build that actually has the file next to it.
        if os.path.isfile(LICENSE_PATH):
            QDesktopServices.openUrl(QUrl.fromLocalFile(LICENSE_PATH))
        else:
            QDesktopServices.openUrl(QUrl(LICENSE_URL))
