import sys

from PySide6.QtWidgets import QApplication

from market_viewer.ui.main_window import MainWindow
from market_viewer.ui.styles import build_app_stylesheet


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Market Viewer")
    app.setStyle("Fusion")
    app.setStyleSheet(build_app_stylesheet())

    window = MainWindow()
    window.show()
    return app.exec()
