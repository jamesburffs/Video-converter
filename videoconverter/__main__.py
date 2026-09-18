import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ._version import __version__
from .main_window import MainWindow

ICON_PATH = os.path.join(os.path.dirname(__file__), "icons", "vidkonverter-app-icon.png")

# A packaged Linux build renders with Qt's generic Fusion style rather than
# a desktop's native one (e.g. KDE's Breeze) - PyInstaller bundles its own
# copy of Qt's plugins, and the distro-specific style plugin isn't part of
# the PySide6 pip wheel, so it's simply not there to bundle. This was tried
# once already: pointing the frozen build at the *system's* Qt plugin
# directory as well (so it could find and load the system's own style
# plugin) let it load a style plugin like Breeze, but that plugin then
# pulls in the system's own Qt6/KDE Frameworks libraries (and whatever
# *those* link against) into a process that already has PyInstaller's own,
# differently-built copies of those same libraries loaded - two
# incompatible builds of the same shared libraries in one process, which
# crashed on launch (SIGABRT, glibc/zlib-ng involved in the trace) on a
# real system. Qt's plugin loader only guards against a *Qt-version*
# mismatch in the plugin itself; it has no way to guard against this kind
# of transitive ABI clash further down the dependency chain. Fusion is the
# safe, working tradeoff for a genuinely portable single-file build -
# proper native theming would need a different distribution model
# entirely (e.g. Flatpak, or the .deb/.rpm route depending on a
# consistent system Qt), not a runtime plugin-path hack on top of a
# frozen, self-contained one.


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("VidKonverter")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(ICON_PATH))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
