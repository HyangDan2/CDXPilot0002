from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from market_viewer.models import ReportRow
from market_viewer.ui.widgets import ReportTableWidget


class AnalysisPanel(QWidget):
    analyze_requested = Signal(str)
    clear_requested = Signal()
    send_context_requested = Signal()
    send_result_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        layout.addWidget(self.tabs)

        report_tab = QWidget()
        report_layout = QVBoxLayout(report_tab)
        report_hint = QLabel("세션 상태, 차트 범위, 기술 지표 리포트를 확인합니다.")
        report_hint.setObjectName("mutedLabel")
        report_layout.addWidget(report_hint)

        report_button_row = QHBoxLayout()
        self.send_context_button = QPushButton("Telegram 발송")
        self.send_context_button.clicked.connect(self.send_context_requested.emit)
        report_button_row.addWidget(self.send_context_button)
        report_button_row.addStretch(1)
        report_layout.addLayout(report_button_row)

        self.context_browser = QTextBrowser()
        self.context_browser.setOpenExternalLinks(True)
        report_layout.addWidget(self.context_browser)

        self.context_table = ReportTableWidget()
        report_layout.addWidget(self.context_table)

        llm_tab = QWidget()
        llm_layout = QVBoxLayout(llm_tab)
        prompt_hint = QLabel("선택 종목을 바탕으로 LLM 분석을 요청하고 Markdown 결과를 확인합니다.")
        prompt_hint.setObjectName("mutedLabel")
        llm_layout.addWidget(prompt_hint)

        self.prompt_editor = QPlainTextEdit()
        self.prompt_editor.setPlaceholderText("예: 이 종목의 추세와 리스크를 요약해줘.")
        self.prompt_editor.setMinimumHeight(150)
        llm_layout.addWidget(self.prompt_editor)

        button_row = QHBoxLayout()
        self.run_button = QPushButton("분석 실행")
        self.run_button.clicked.connect(self._emit_analyze_request)
        self.clear_button = QPushButton("출력 지우기")
        self.clear_button.clicked.connect(self.clear_requested.emit)
        button_row.addWidget(self.run_button)
        self.send_result_button = QPushButton("Telegram 발송")
        self.send_result_button.clicked.connect(self.send_result_requested.emit)
        button_row.addWidget(self.send_result_button)
        button_row.addWidget(self.clear_button)
        llm_layout.addLayout(button_row)

        self.result_browser = QTextBrowser()
        self.result_browser.setOpenExternalLinks(True)
        llm_layout.addWidget(self.result_browser)

        self.tabs.addTab(report_tab, "세션 요약과 기술 리포트")
        self.tabs.addTab(llm_tab, "LLM 프롬프트와 Markdown")

    def set_context_markdown(self, markdown: str) -> None:
        self.context_browser.document().setMarkdown(markdown)

    def set_result_markdown(self, markdown: str) -> None:
        self.result_browser.document().setMarkdown(markdown)

    def set_context_table_rows(self, rows: list[ReportRow]) -> None:
        self.context_table.set_report_rows(rows)

    def set_user_request_text(self, text: str) -> None:
        self.prompt_editor.setPlainText(text)

    def user_request_text(self) -> str:
        return self.prompt_editor.toPlainText().strip()

    def context_markdown(self) -> str:
        return self.context_browser.toPlainText().strip()

    def result_markdown(self) -> str:
        return self.result_browser.toPlainText().strip()

    def focus_prompt_editor(self) -> None:
        self.tabs.setCurrentIndex(1)
        self.prompt_editor.setFocus()

    def _emit_analyze_request(self) -> None:
        self.tabs.setCurrentIndex(1)
        self.analyze_requested.emit(self.user_request_text())
