from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from market_viewer.analysis.condition_parser import (
    METRIC_DEFINITIONS,
    default_screening_conditions,
    format_ma_above,
    format_ma_order,
    parse_ma_above,
    parse_ma_order,
    parse_metric_rules,
    summarize_conditions,
)
from market_viewer.analysis.filter_models import ScreeningCondition


COLUMNS = ["사용", "결합", "조건명", "MA 정배열", "MA 비교"] + [f"{label} 조건" for label, _ in METRIC_DEFINITIONS]


class ScreeningDialog(QDialog):
    def __init__(self, conditions: list[ScreeningCondition], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("스크리닝 조건식 편집")
        self.resize(1500, 620)
        self._conditions = conditions
        self._setup_ui()
        self._load_conditions(conditions)
        self._sync_summary()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        help_label = QLabel(
            "조건 행마다 AND/OR를 선택합니다. MA 정배열 예: 5>20>60, MA 비교 예: 5>120. "
            "지표 조건 예: <5, >10, >=0, <=100000. 복수 조건은 >2,<10처럼 콤마로 입력합니다."
        )
        help_label.setWordWrap(True)
        help_label.setObjectName("mutedLabel")
        layout.addWidget(help_label)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self._sync_summary)
        layout.addWidget(self.table, 1)

        button_row = QHBoxLayout()
        self.add_button = QPushButton("행 추가")
        self.preset_button = QPushButton("프리셋 불러오기")
        self.remove_button = QPushButton("선택 행 삭제")
        self.save_button = QPushButton("저장 후 적용")
        self.cancel_button = QPushButton("취소")
        self.add_button.clicked.connect(self.add_empty_row)
        self.preset_button.clicked.connect(self.load_presets)
        self.remove_button.clicked.connect(self.remove_selected)
        self.save_button.clicked.connect(self.on_save)
        self.cancel_button.clicked.connect(self.reject)
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.preset_button)
        button_row.addWidget(self.remove_button)
        button_row.addStretch(1)
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.cancel_button)
        layout.addLayout(button_row)

        self.summary_label = QLabel("조건 없음")
        self.summary_label.setWordWrap(True)
        self.summary_label.setObjectName("mutedLabel")
        layout.addWidget(self.summary_label)

    def conditions(self) -> list[ScreeningCondition]:
        return self._conditions

    def add_empty_row(self) -> None:
        self.add_condition_row(ScreeningCondition(name="custom_condition", operand="AND"))

    def load_presets(self) -> None:
        self._load_conditions(default_screening_conditions())

    def remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
        self._sync_summary()

    def add_condition_row(self, condition: ScreeningCondition) -> None:
        self.table.blockSignals(True)
        row = self.table.rowCount()
        self.table.insertRow(row)

        enabled = QCheckBox()
        enabled.setChecked(condition.enabled)
        enabled.setStyleSheet("margin-left: 24px;")
        enabled.toggled.connect(self._sync_summary)
        self.table.setCellWidget(row, 0, enabled)

        operand = QComboBox()
        operand.addItems(["AND", "OR"])
        operand.setCurrentText((condition.operand or "AND").upper())
        operand.currentIndexChanged.connect(self._sync_summary)
        self.table.setCellWidget(row, 1, operand)

        self.table.setItem(row, 2, QTableWidgetItem(condition.name))
        self.table.setItem(row, 3, QTableWidgetItem(format_ma_order(condition.ma_order)))
        self.table.setItem(row, 4, QTableWidgetItem(format_ma_above(condition.ma_above)))

        metric_values: dict[str, list[str]] = {}
        for rule in condition.metrics:
            metric_values.setdefault(rule.metric, []).append(f"{rule.op}{rule.value:g}")
        for index, (_, metric) in enumerate(METRIC_DEFINITIONS, start=5):
            self.table.setItem(row, index, QTableWidgetItem(",".join(metric_values.get(metric, []))))
        self.table.blockSignals(False)

    def collect_conditions(self) -> list[ScreeningCondition]:
        conditions: list[ScreeningCondition] = []
        for row in range(self.table.rowCount()):
            enabled_widget = self.table.cellWidget(row, 0)
            operand_widget = self.table.cellWidget(row, 1)
            enabled = enabled_widget.isChecked() if isinstance(enabled_widget, QCheckBox) else True
            operand = operand_widget.currentText() if isinstance(operand_widget, QComboBox) else "AND"
            name = self._cell_text(row, 2)
            if not name:
                raise ValueError(f"{row + 1}행: 조건명을 입력하세요.")
            metrics = []
            for offset, (_, metric) in enumerate(METRIC_DEFINITIONS, start=5):
                metrics.extend(parse_metric_rules(metric, self._cell_text(row, offset)))
            conditions.append(
                ScreeningCondition(
                    name=name,
                    enabled=enabled,
                    operand=operand,
                    ma_order=parse_ma_order(self._cell_text(row, 3)),
                    ma_above=parse_ma_above(self._cell_text(row, 4)),
                    metrics=metrics,
                )
            )
        return conditions

    def on_save(self) -> None:
        try:
            conditions = self.collect_conditions()
            if not conditions:
                QMessageBox.warning(self, "조건 없음", "최소 하나 이상의 조건 행이 필요합니다.")
                return
            self._conditions = conditions
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "조건식 오류", str(exc))

    def _load_conditions(self, conditions: list[ScreeningCondition]) -> None:
        self.table.setRowCount(0)
        for condition in conditions:
            self.add_condition_row(condition)
        self._sync_summary()

    def _sync_summary(self) -> None:
        try:
            summary = summarize_conditions(self.collect_conditions())
        except Exception:
            summary = "조건식 편집 중..."
        self.summary_label.setText(summary)

    def _cell_text(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text().strip() if item else ""
