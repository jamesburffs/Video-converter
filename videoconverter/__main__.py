import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ._version import __version__
from .external_env import ensure_macos_homebrew_on_path
from .main_window import MainWindow
from .theme import apply_theme

ICON_PATH = os.path.join(os.path.dirname(__file__), "icons", "vidkonverter-app-icon.png")


def main():
    # Before anything else touches PATH-based detection (ffmpeg/ffprobe
    # availability, the FFmpeg Setup dialog's Homebrew check) - see
    # external_env.py for why this is needed on macOS specifically.
    ensure_macos_homebrew_on_path()

    app = QApplication(sys.argv)
    # Explicit Fusion + a hard-coded palette, applied before any window is
    # built - see theme.py for why (in short: a native style like KDE's
    # Breeze isn't safely bundle-able in a frozen build, and leaving each
    # platform to its own default style made Linux and macOS builds look,
    # and even lay out, differently from each other).
    apply_theme(app)
    app.setApplicationName("VidKonverter")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(ICON_PATH))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
