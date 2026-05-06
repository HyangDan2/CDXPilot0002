from __future__ import annotations

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from market_viewer.models import StockReference


class StockTableModel(QAbstractTableModel):
    headers = ["시장", "코드", "종목명", "통화", "종가", "등락률"]
    fields = ["Market", "Code", "Name", "Currency", "Close", "ChangePct"]

    def __init__(self) -> None:
        super().__init__()
        self._frame = pd.DataFrame(columns=self.fields)

    def set_frame(self, frame: pd.DataFrame) -> None:
        self.beginResetModel()
        self._frame = frame.reset_index(drop=True).copy()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._frame)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self.headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid() or index.row() >= len(self._frame):
            return None
        if role == Qt.ItemDataRole.UserRole:
            return self.stock_at(index.row())
        if role == Qt.ItemDataRole.TextAlignmentRole and index.column() in (4, 5):
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        row = self._frame.iloc[index.row()]
        field = self.fields[index.column()]
        value = row.get(field)
        if field == "Close":
            return f"{value:,.0f}" if pd.notna(value) else "-"
        if field == "ChangePct":
            return f"{value:.2f}%" if pd.notna(value) else "-"
        return str(value) if pd.notna(value) else ""

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None

    def stock_at(self, row: int) -> StockReference | None:
        if row < 0 or row >= len(self._frame):
            return None
        data = self._frame.iloc[row]
        return StockReference(
            code=str(data.get("Code", "")),
            name=str(data.get("Name", "")),
            market=str(data.get("Market", "")),
            country=str(data.get("Country", "")),
            currency=str(data.get("Currency", "")),
        )

    def code_at(self, row: int) -> str:
        stock = self.stock_at(row)
        return stock.code if stock is not None else ""


class StockListPanel(QWidget):
    market_scope_changed = Signal(str)
    refresh_requested = Signal()
    stock_activated = Signal(object)
    search_failed = Signal(str)
    stop_screen_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._frame = pd.DataFrame()
        self._view_frame = pd.DataFrame()
        self._model = StockTableModel()
        self._filter_prompt = ""
        self._is_updating_table = False
        self._suppress_selection_activation = False
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
        self.market_combo.setMinimumWidth(190)
        self.market_combo.currentIndexChanged.connect(self._emit_market_scope_changed)
        self.refresh_button = QPushButton("새로고침")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        market_row.addWidget(self.market_combo)
        market_row.addWidget(self.refresh_button)
        layout.addLayout(market_row)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("종목명 또는 코드 검색")
        self.search_input.textChanged.connect(self._apply_view_filter)
        self.search_input.returnPressed.connect(self.activate_search_result)
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

        progress_row = QHBoxLayout()
        self.screen_progress_label = QLabel("스크리닝 대기")
        self.screen_progress_label.setObjectName("mutedLabel")
        self.stop_screen_button = QPushButton("Stop")
        self.stop_screen_button.setEnabled(False)
        self.stop_screen_button.clicked.connect(self.stop_screen_requested.emit)
        progress_row.addWidget(self.screen_progress_label, 1)
        progress_row.addWidget(self.stop_screen_button)
        layout.addLayout(progress_row)

        self.table = QTableView()
        self.table.setModel(self._model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.selectionModel().selectionChanged.connect(self._handle_selection_changed)
        self.table.clicked.connect(self._emit_selected_stock)
        self.table.doubleClicked.connect(self._emit_selected_stock)
        layout.addWidget(self.table)

    def set_market_options(self, options: list[tuple[str, str]]) -> None:
        self.market_combo.blockSignals(True)
        self.market_combo.clear()
        for market_id, label in options:
            self.market_combo.addItem(label, market_id)
            self.market_combo.setItemData(self.market_combo.count() - 1, market_id, Qt.ItemDataRole.ToolTipRole)
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

    def set_listing_loading(self, loading: bool) -> None:
        self.refresh_button.setEnabled(not loading)
        self.market_combo.setEnabled(not loading)

    def set_screening_running(self, running: bool) -> None:
        self.stop_screen_button.setEnabled(running)

    def set_screening_progress(self, text: str) -> None:
        self.screen_progress_label.setText(text)

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
        row = self._current_row()
        if row < 0:
            return None
        return self._model.stock_at(row)

    def activate_current_selection(self) -> None:
        stock = self.current_stock()
        if stock is not None:
            self.stock_activated.emit(stock)

    def activate_search_result(self) -> None:
        if self._model.rowCount() == 0:
            self.search_failed.emit("검색 결과가 없습니다.")
            return

        query = self.search_input.text().strip()
        if query.isdigit():
            normalized_code = query.zfill(6)
            for row in range(self._model.rowCount()):
                if self._model.code_at(row) == normalized_code:
                    self._activate_row(row)
                    return

        current_row = self._current_row()
        self._activate_row(current_row if current_row >= 0 else 0)

    def select_relative_row(self, offset: int, activate: bool = False) -> None:
        row_count = self._model.rowCount()
        if row_count == 0:
            return
        current = max(0, self._current_row())
        new_row = min(row_count - 1, max(0, current + offset))
        self.table.selectRow(new_row)
        if activate:
            self.activate_current_selection()

    def select_stock(self, stock: StockReference) -> None:
        for row in range(self._model.rowCount()):
            data = self._model.stock_at(row)
            if data is not None and data.code == stock.code and data.market == stock.market:
                self.table.selectRow(row)
                break

    def _apply_view_filter(self, auto_activate: bool = True) -> None:
        self._is_updating_table = True
        try:
            query = self.search_input.text().strip().lower()
            filtered = self._frame
            required_columns = {"Name", "Code", "Market"}
            if filtered.empty or not required_columns.issubset(filtered.columns):
                self._view_frame = pd.DataFrame()
                self._model.set_frame(self._view_frame)
                self.count_label.setText("0 종목")
                return
            if query:
                mask = (
                    filtered["Name"].astype(str).str.lower().str.contains(query, na=False, regex=False)
                    | filtered["Code"].astype(str).str.lower().str.contains(query, na=False, regex=False)
                    | filtered["Market"].astype(str).str.lower().str.contains(query, na=False, regex=False)
                )
                filtered = filtered[mask]

            self._view_frame = filtered.reset_index(drop=True)
            self.table.setUpdatesEnabled(False)
            try:
                self._model.set_frame(self._view_frame)
                if len(self._view_frame) > 0:
                    self.table.selectRow(0)
                else:
                    self.table.clearSelection()
            finally:
                self.table.setUpdatesEnabled(True)

            self.count_label.setText(f"{len(self._view_frame)} 종목")
        finally:
            self._is_updating_table = False

        if len(self._view_frame) > 0 and auto_activate:
            self.activate_current_selection()

    def _activate_row(self, row: int) -> None:
        if row < 0 or row >= self._model.rowCount():
            self.search_failed.emit("선택할 종목이 없습니다.")
            return
        self._suppress_selection_activation = True
        try:
            self.table.selectRow(row)
        finally:
            self._suppress_selection_activation = False
        self.activate_current_selection()

    def _emit_market_scope_changed(self) -> None:
        self.market_scope_changed.emit(self.current_market_scope())

    def _emit_selected_stock(self, index: QModelIndex) -> None:
        stock = self._model.stock_at(index.row())
        if stock is not None:
            self.stock_activated.emit(stock)

    def _handle_selection_changed(self) -> None:
        if self._is_updating_table or self._suppress_selection_activation:
            return
        self.activate_current_selection()

    def _current_row(self) -> int:
        index = self.table.currentIndex()
        return index.row() if index.isValid() else -1
