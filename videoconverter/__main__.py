import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ._version import __version__
from .main_window import MainWindow

ICON_PATH = os.path.join(os.path.dirname(__file__), "icons", "vidkonverter-app-icon.png")


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
