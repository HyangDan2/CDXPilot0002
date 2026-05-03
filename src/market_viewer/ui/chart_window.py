from __future__ import annotations

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow

from market_viewer.ui.chart_panel import ChartPanel


class ChartWindow(QMainWindow):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._allow_close = False
        self.chart_panel = ChartPanel()
        self.setWindowTitle("차트")
        self.resize(1120, 820)
        self.setCentralWidget(self.chart_panel)

    def reveal(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def prepare_for_shutdown(self) -> None:
        self._allow_close = True
        self.chart_panel.begin_shutdown()
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            super().closeEvent(event)
            return
        self.hide()
        event.ignore()
