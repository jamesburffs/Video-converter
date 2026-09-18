import os
import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ._version import __version__
from .main_window import MainWindow

ICON_PATH = os.path.join(os.path.dirname(__file__), "icons", "vidkonverter-app-icon.png")


def _add_system_qt_plugin_paths():
    """PyInstaller bundles PySide6's own Qt plugins, which don't include a
    desktop's native widget style (e.g. KDE's Breeze) - that's shipped by
    the distro's own Qt packages, not the PySide6 pip wheel, and was never
    present on the CI runner that built this binary to bundle in the first
    place. A from-source run already picks up the system's Qt installation
    directly and doesn't need this; a frozen build only searches its own
    bundled copy unless told to also look here. Linux only - Windows/macOS
    have no equivalent "system Qt style" to find, and the bundled Qt
    already covers those natively. Best-effort: Qt's plugin loader checks
    each plugin's build version against its own before loading it, so a
    system Qt version too different from the one bundled here is silently
    skipped rather than crashing - worst case this changes nothing and the
    bundled Fusion style remains the fallback, same as without it."""
    if not (getattr(sys, "frozen", False) and sys.platform.startswith("linux")):
        return
    env_paths = [p for p in os.environ.get("QT_PLUGIN_PATH", "").split(os.pathsep) if p]
    candidates = env_paths + [
        "/usr/lib64/qt6/plugins",
        "/usr/lib/qt6/plugins",
        "/usr/lib/x86_64-linux-gnu/qt6/plugins",
        "/usr/lib/aarch64-linux-gnu/qt6/plugins",
    ]
    for path in candidates:
        if os.path.isdir(path):
            QCoreApplication.addLibraryPath(path)


def main():
    _add_system_qt_plugin_paths()
    app = QApplication(sys.argv)
    app.setApplicationName("VidKonverter")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(ICON_PATH))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
