from __future__ import annotations


def build_app_stylesheet() -> str:
    return """
    QWidget {
        background: #f5f7fb;
        color: #16202a;
        font-size: 13px;
        font-family: "Helvetica Neue";
    }

    QMainWindow::separator {
        background: #d7dee8;
        width: 1px;
        height: 1px;
    }

    QMenuBar {
        background: #ffffff;
        border-bottom: 1px solid #d7dee8;
    }

    QMenuBar::item {
        padding: 6px 10px;
        background: transparent;
    }

    QMenuBar::item:selected {
        background: #e8f0ff;
        border-radius: 6px;
    }

    QMenu {
        background: #ffffff;
        border: 1px solid #d7dee8;
        padding: 6px;
    }

    QMenu::item {
        padding: 6px 22px;
        border-radius: 6px;
    }

    QMenu::item:selected {
        background: #e8f0ff;
    }

    QStatusBar {
        background: #ffffff;
        border-top: 1px solid #d7dee8;
    }

    QTabWidget::pane {
        border: 1px solid #d7dee8;
        background: #ffffff;
        border-radius: 10px;
    }

    QTabBar::tab {
        background: #edf1f7;
        padding: 8px 14px;
        margin-right: 4px;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
    }

    QTabBar::tab:selected {
        background: #ffffff;
    }

    QLineEdit, QPlainTextEdit, QTextBrowser, QComboBox, QTableWidget {
        background: #ffffff;
        border: 1px solid #d7dee8;
        border-radius: 10px;
    }

    QLineEdit, QComboBox {
        min-height: 34px;
        padding: 0 10px;
    }

    QPlainTextEdit, QTextBrowser {
        padding: 8px 10px;
    }

    QComboBox::drop-down {
        border: none;
        width: 24px;
    }

    QPushButton {
        background: #1f6feb;
        color: #ffffff;
        border: none;
        border-radius: 10px;
        padding: 8px 14px;
        min-height: 34px;
        font-weight: 600;
    }

    QPushButton:hover {
        background: #1a63d6;
    }

    QPushButton:pressed {
        background: #1556bc;
    }

    QPushButton:disabled {
        background: #b9c4d6;
        color: #eef2f7;
    }

    QTableWidget {
        gridline-color: #edf1f7;
        alternate-background-color: #f8fafc;
        selection-background-color: #dbe8ff;
        selection-color: #16202a;
    }

    QHeaderView::section {
        background: #f8fafc;
        border: none;
        border-bottom: 1px solid #d7dee8;
        padding: 8px 10px;
        font-weight: 700;
    }

    QLabel#panelTitle {
        font-size: 18px;
        font-weight: 700;
        color: #16202a;
    }

    QLabel#sectionLabel {
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.3px;
        color: #58667a;
        margin-top: 2px;
    }

    QLabel#mutedLabel {
        color: #6b778c;
        font-size: 12px;
    }
    """
