from __future__ import annotations

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from market_viewer.models import StockReference


class StockListPanel(QWidget):
    market_scope_changed = Signal(str)
    refresh_requested = Signal()
    stock_activated = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._frame = pd.DataFrame()
        self._filter_prompt = ""
        self._is_updating_table = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("시장 스크리너")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        market_row = QHBoxLayout()
        market_label = QLabel("시장 범위")
        market_label.setObjectName("sectionLabel")
        market_row.addWidget(market_label)
        self.market_combo = QComboBox()
        self.market_combo.currentIndexChanged.connect(self._emit_market_scope_changed)
        self.refresh_button = QPushButton("새로고침")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        market_row.addWidget(self.market_combo)
        market_row.addWidget(self.refresh_button)
        layout.addLayout(market_row)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("종목명 또는 코드 검색")
        self.search_input.textChanged.connect(self._apply_view_filter)
        layout.addWidget(self.search_input)

        resolved_title = QLabel("적용 조건")
        resolved_title.setObjectName("sectionLabel")
        layout.addWidget(resolved_title)
        self.screen_summary_label = QLabel("조건 없음")
        self.screen_summary_label.setObjectName("mutedLabel")
        self.screen_summary_label.setWordWrap(True)
        layout.addWidget(self.screen_summary_label)

        summary_row = QHBoxLayout()
        self.count_label = QLabel("0 종목")
        self.count_label.setObjectName("mutedLabel")
        summary_row.addWidget(self.count_label)
        summary_row.addStretch(1)
        layout.addLayout(summary_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["시장", "코드", "종목명", "통화", "종가", "등락률"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._handle_selection_changed)
        self.table.cellClicked.connect(self._emit_selected_stock)
        self.table.cellDoubleClicked.connect(self._emit_selected_stock)
        layout.addWidget(self.table)

    def set_market_options(self, options: list[tuple[str, str]]) -> None:
        self.market_combo.blockSignals(True)
        self.market_combo.clear()
        for market_id, label in options:
            self.market_combo.addItem(label, market_id)
        self.market_combo.blockSignals(False)

    def set_market_scope(self, market_scope: str) -> None:
        index = self.market_combo.findData(market_scope)
        if index >= 0:
            self.market_combo.blockSignals(True)
            self.market_combo.setCurrentIndex(index)
            self.market_combo.blockSignals(False)

    def current_market_scope(self) -> str:
        return str(self.market_combo.currentData())

    def set_listing(self, frame: pd.DataFrame, auto_activate: bool = True) -> None:
        self._frame = frame.copy()
        self._apply_view_filter(auto_activate=auto_activate)

    def set_filter_prompt(self, prompt: str) -> None:
        self._filter_prompt = prompt.strip()

    def set_resolved_preview(self, markdown: str) -> None:
        text = markdown.replace("#", "").replace("*", "").strip()
        self.screen_summary_label.setText(text or "조건 없음")

    def set_apply_enabled(self, enabled: bool) -> None:
        return

    def filter_prompt(self) -> str:
        return self._filter_prompt

    def focus_filter_prompt(self) -> None:
        self.table.setFocus()

    def focus_search(self) -> None:
        self.search_input.setFocus()

    def focus_market_scope(self) -> None:
        self.market_combo.setFocus()

    def focus_table(self) -> None:
        self.table.setFocus()

    def trigger_interpret(self) -> None:
        return

    def trigger_apply(self) -> None:
        return

    def trigger_clear(self) -> None:
        return

    def current_stock(self) -> StockReference | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        data = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        return data

    def activate_current_selection(self) -> None:
        stock = self.current_stock()
        if stock is not None:
            self.stock_activated.emit(stock)

    def select_relative_row(self, offset: int, activate: bool = False) -> None:
        if self.table.rowCount() == 0:
            return
        current = max(0, self.table.currentRow())
        new_row = min(self.table.rowCount() - 1, max(0, current + offset))
        self.table.selectRow(new_row)
        if activate:
            self.activate_current_selection()

    def select_stock(self, stock: StockReference) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            data = item.data(Qt.ItemDataRole.UserRole) if item else None
            if isinstance(data, StockReference) and data.code == stock.code and data.market == stock.market:
                self.table.selectRow(row)
                break

    def _apply_view_filter(self, auto_activate: bool = True) -> None:
        self._is_updating_table = True
        query = self.search_input.text().strip().lower()
        filtered = self._frame
        if query:
            mask = (
                filtered["Name"].astype(str).str.lower().str.contains(query, na=False)
                | filtered["Code"].astype(str).str.lower().str.contains(query, na=False)
                | filtered["Market"].astype(str).str.lower().str.contains(query, na=False)
            )
            filtered = filtered[mask]

        self.table.setRowCount(len(filtered))
        for row_index, (_, row) in enumerate(filtered.iterrows()):
            stock = StockReference(
                code=str(row.get("Code", "")),
                name=str(row.get("Name", "")),
                market=str(row.get("Market", "")),
                country=str(row.get("Country", "")),
                currency=str(row.get("Currency", "")),
            )
            values = [
                stock.market,
                stock.code,
                stock.name,
                stock.currency,
                f"{row.get('Close'):,.0f}" if pd.notna(row.get("Close")) else "-",
                f"{row.get('ChangePct'):.2f}%" if pd.notna(row.get("ChangePct")) else "-",
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column_index in (4, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if column_index == 0:
                    item.setData(Qt.ItemDataRole.UserRole, stock)
                self.table.setItem(row_index, column_index, item)

        if len(filtered) > 0:
            self.table.selectRow(0)
        self.count_label.setText(f"{len(filtered)} 종목")
        self._is_updating_table = False

        if len(filtered) > 0 and auto_activate:
            self.activate_current_selection()

    def _emit_market_scope_changed(self) -> None:
        self.market_scope_changed.emit(self.current_market_scope())

    def _emit_selected_stock(self, row: int, _: int) -> None:
        item = self.table.item(row, 0)
        if item:
            stock = item.data(Qt.ItemDataRole.UserRole)
            if stock is not None:
                self.stock_activated.emit(stock)

    def _handle_selection_changed(self) -> None:
        if self._is_updating_table:
            return
        self.activate_current_selection()
