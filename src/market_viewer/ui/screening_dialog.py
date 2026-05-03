from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from market_viewer.analysis.filter_parser import parse_filter_prompt

_CROSS_OPTIONS: list[tuple[str, str]] = [
    ("사용 안 함", ""),
    ("MA5 crosses above MA20", "ma5 golden cross ma20"),
    ("MA20 crosses above MA60", "ma20 golden cross ma60"),
    ("MA20 crosses above MA224", "ma20 golden cross ma224"),
    ("MA60 crosses above MA224", "ma60 golden cross ma224"),
]


class ScreeningDialog(QDialog):
    def __init__(self, current_prompt: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("스크리닝 조건 편집")
        self.resize(520, 420)
        self._setup_ui()
        self._load_from_prompt(current_prompt)
        self._sync_summary()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        intro = QLabel("메뉴바 중심 스크리닝을 위해 조건을 구조화해서 관리합니다.")
        intro.setWordWrap(True)
        intro.setObjectName("mutedLabel")
        layout.addWidget(intro)

        trend_group = QGroupBox("추세 / 정렬")
        trend_form = QFormLayout(trend_group)
        self.bullish_check = QCheckBox("정배열 (MA5 > MA20 > MA60 > MA224)")
        self.bearish_check = QCheckBox("역배열 (MA5 < MA20 < MA60 < MA224)")
        self.price_above_224_check = QCheckBox("종가가 MA224 위")
        trend_form.addRow(self.bullish_check)
        trend_form.addRow(self.bearish_check)
        trend_form.addRow(self.price_above_224_check)
        layout.addWidget(trend_group)

        cross_group = QGroupBox("골든크로스")
        cross_form = QFormLayout(cross_group)
        self.cross_combo = QComboBox()
        for label, value in _CROSS_OPTIONS:
            self.cross_combo.addItem(label, value)
        cross_form.addRow("조건", self.cross_combo)
        layout.addWidget(cross_group)

        momentum_group = QGroupBox("모멘텀 / 거래량")
        momentum_form = QFormLayout(momentum_group)
        self.volume_check = QCheckBox("거래량 20일 평균 대비")
        self.volume_spin = QDoubleSpinBox()
        self.volume_spin.setRange(1.0, 20.0)
        self.volume_spin.setDecimals(1)
        self.volume_spin.setSingleStep(0.1)
        self.volume_spin.setValue(1.5)
        volume_row = QHBoxLayout()
        volume_row.addWidget(self.volume_check)
        volume_row.addWidget(self.volume_spin)
        volume_row.addWidget(QLabel("배 이상"))
        momentum_form.addRow(volume_row)

        self.new_high_check = QCheckBox("60일 신고가")
        momentum_form.addRow(self.new_high_check)

        layout.addWidget(momentum_group)

        fundamental_group = QGroupBox("키움 기본정보 / 재무 스냅샷")
        fundamental_form = QFormLayout(fundamental_group)
        self.per_check = QCheckBox("PER <=")
        self.per_spin = QDoubleSpinBox()
        self.per_spin.setRange(0.0, 500.0)
        self.per_spin.setDecimals(1)
        self.per_spin.setValue(20.0)
        per_row = QHBoxLayout()
        per_row.addWidget(self.per_check)
        per_row.addWidget(self.per_spin)
        fundamental_form.addRow(per_row)

        self.pbr_check = QCheckBox("PBR <=")
        self.pbr_spin = QDoubleSpinBox()
        self.pbr_spin.setRange(0.0, 50.0)
        self.pbr_spin.setDecimals(2)
        self.pbr_spin.setValue(3.0)
        pbr_row = QHBoxLayout()
        pbr_row.addWidget(self.pbr_check)
        pbr_row.addWidget(self.pbr_spin)
        fundamental_form.addRow(pbr_row)

        self.roe_check = QCheckBox("ROE >=")
        self.roe_spin = QDoubleSpinBox()
        self.roe_spin.setRange(-100.0, 200.0)
        self.roe_spin.setDecimals(1)
        self.roe_spin.setValue(5.0)
        roe_row = QHBoxLayout()
        roe_row.addWidget(self.roe_check)
        roe_row.addWidget(self.roe_spin)
        fundamental_form.addRow(roe_row)

        self.operating_profit_check = QCheckBox("영업이익 양수")
        self.net_income_check = QCheckBox("순이익 양수")
        fundamental_form.addRow(self.operating_profit_check)
        fundamental_form.addRow(self.net_income_check)
        layout.addWidget(fundamental_group)

        preset_row = QHBoxLayout()
        bullish_button = QPushButton("Bullish 프리셋")
        bearish_button = QPushButton("Bearish 프리셋")
        golden_button = QPushButton("GC 프리셋")
        clear_button = QPushButton("조건 비우기")
        bullish_button.clicked.connect(self._apply_bullish_preset)
        bearish_button.clicked.connect(self._apply_bearish_preset)
        golden_button.clicked.connect(self._apply_golden_preset)
        clear_button.clicked.connect(self._reset_conditions)
        preset_row.addWidget(bullish_button)
        preset_row.addWidget(bearish_button)
        preset_row.addWidget(golden_button)
        preset_row.addWidget(clear_button)
        layout.addLayout(preset_row)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.summary_label)

        for widget in [
            self.bullish_check,
            self.bearish_check,
            self.price_above_224_check,
            self.volume_check,
            self.new_high_check,
            self.per_check,
            self.pbr_check,
            self.roe_check,
            self.operating_profit_check,
            self.net_income_check,
        ]:
            widget.toggled.connect(self._sync_summary)
        for widget in [self.volume_spin, self.per_spin, self.pbr_spin, self.roe_spin]:
            widget.valueChanged.connect(self._sync_summary)
        self.cross_combo.currentIndexChanged.connect(self._sync_summary)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def screening_prompt(self) -> str:
        parts: list[str] = []
        if self.bullish_check.isChecked():
            parts.append("bullish alignment")
        if self.bearish_check.isChecked():
            parts.append("bearish alignment")
        if self.price_above_224_check.isChecked():
            parts.append("224일선 위")
        cross_prompt = str(self.cross_combo.currentData() or "")
        if cross_prompt:
            parts.append(cross_prompt)
        if self.volume_check.isChecked():
            parts.append(f"거래량 {self.volume_spin.value():g}배 이상")
        if self.new_high_check.isChecked():
            parts.append("60일 신고가")
        if self.per_check.isChecked():
            parts.append(f"per <= {self.per_spin.value():g}")
        if self.pbr_check.isChecked():
            parts.append(f"pbr <= {self.pbr_spin.value():g}")
        if self.roe_check.isChecked():
            parts.append(f"roe >= {self.roe_spin.value():g}")
        if self.operating_profit_check.isChecked():
            parts.append("영업이익 양수")
        if self.net_income_check.isChecked():
            parts.append("순이익 양수")
        return " / ".join(parts)

    def _sync_summary(self) -> None:
        summary = self.screening_prompt() or "조건 없음"
        self.summary_label.setText(f"현재 조건식\n{summary}")

    def _apply_bullish_preset(self) -> None:
        self._reset_conditions()
        self.bullish_check.setChecked(True)
        self.price_above_224_check.setChecked(True)
        self.volume_check.setChecked(True)
        self.volume_spin.setValue(1.3)

    def _apply_bearish_preset(self) -> None:
        self._reset_conditions()
        self.bearish_check.setChecked(True)

    def _apply_golden_preset(self) -> None:
        self._reset_conditions()
        self.cross_combo.setCurrentIndex(self.cross_combo.findData("ma20 golden cross ma60"))
        self.volume_check.setChecked(True)
        self.volume_spin.setValue(1.5)

    def _reset_conditions(self) -> None:
        self.bullish_check.setChecked(False)
        self.bearish_check.setChecked(False)
        self.price_above_224_check.setChecked(False)
        self.cross_combo.setCurrentIndex(0)
        self.volume_check.setChecked(False)
        self.new_high_check.setChecked(False)
        self.per_check.setChecked(False)
        self.pbr_check.setChecked(False)
        self.roe_check.setChecked(False)
        self.operating_profit_check.setChecked(False)
        self.net_income_check.setChecked(False)

    def _load_from_prompt(self, prompt: str) -> None:
        if not prompt.strip():
            return
        parsed = parse_filter_prompt(prompt, "KOSPI")
        self._reset_conditions()
        for condition in parsed.conditions:
            if condition.field == "MA_ALIGNMENT":
                if condition.value == "bullish_5_20_60":
                    self.bullish_check.setChecked(True)
                elif condition.value == "bearish_5_20_60":
                    self.bearish_check.setChecked(True)
            elif condition.field == "price_vs_ma" and condition.operator == ">" and int(condition.value) == 224:
                self.price_above_224_check.setChecked(True)
            elif condition.field == "MA_CROSS":
                preset_value = {
                    "golden_5_20": "ma5 golden cross ma20",
                    "golden_20_60": "ma20 golden cross ma60",
                    "golden_20_224": "ma20 golden cross ma224",
                    "golden_60_224": "ma60 golden cross ma224",
                }.get(str(condition.value))
                if preset_value:
                    combo_index = self.cross_combo.findData(preset_value)
                    if combo_index >= 0:
                        self.cross_combo.setCurrentIndex(combo_index)
            elif condition.field == "VolumeRatio" and condition.operator == ">=":
                self.volume_check.setChecked(True)
                self.volume_spin.setValue(float(condition.value))
            elif condition.field == "NEW_HIGH" and int(condition.value) == 60:
                self.new_high_check.setChecked(True)
            elif condition.field == "PER" and condition.operator == "<=":
                self.per_check.setChecked(True)
                self.per_spin.setValue(float(condition.value))
            elif condition.field == "PBR" and condition.operator == "<=":
                self.pbr_check.setChecked(True)
                self.pbr_spin.setValue(float(condition.value))
            elif condition.field == "ROE" and condition.operator == ">=":
                self.roe_check.setChecked(True)
                self.roe_spin.setValue(float(condition.value))
            elif condition.field == "OperatingProfit" and condition.operator == ">":
                self.operating_profit_check.setChecked(True)
            elif condition.field == "NetIncome" and condition.operator == ">":
                self.net_income_check.setChecked(True)
