from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
)

from market_viewer.models import ScreeningReportConfig


class ScreeningReportSettingsDialog(QDialog):
    def __init__(self, config: ScreeningReportConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("보고서/스케줄 설정")
        self._config = config
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.llm_report_interval = QSpinBox()
        self.llm_report_interval.setRange(1, 1440)
        self.llm_report_interval.setSuffix(" min")
        self.llm_report_interval.setValue(self._config.llm_report_interval_minutes)
        form.addRow("LLM report interval", self.llm_report_interval)

        self.scheduled_interval = QSpinBox()
        self.scheduled_interval.setRange(1, 1440)
        self.scheduled_interval.setSuffix(" min")
        self.scheduled_interval.setValue(self._config.scheduled_screening_interval_minutes)
        form.addRow("Scheduled screening interval", self.scheduled_interval)

        self.max_samples = QDoubleSpinBox()
        self.max_samples.setRange(0.1, 100.0)
        self.max_samples.setDecimals(1)
        self.max_samples.setSuffix(" samples/sec")
        self.max_samples.setValue(self._config.max_samples_per_second)
        form.addRow("Screening max speed", self.max_samples)

        self.min_samples = QDoubleSpinBox()
        self.min_samples.setRange(0.1, 100.0)
        self.min_samples.setDecimals(1)
        self.min_samples.setSuffix(" samples/sec")
        self.min_samples.setValue(self._config.min_samples_per_second)
        form.addRow("Adaptive minimum speed", self.min_samples)

        self.adaptive_speed_down = QCheckBox("Enable adaptive slowdown")
        self.adaptive_speed_down.setChecked(self._config.adaptive_speed_down)
        form.addRow("Adaptive slowdown", self.adaptive_speed_down)

        self.max_report_stocks = QSpinBox()
        self.max_report_stocks.setRange(1, 1000)
        self.max_report_stocks.setValue(self._config.max_llm_report_stocks)
        form.addRow("Max queued report stocks", self.max_report_stocks)

        self.max_stock_reports = QSpinBox()
        self.max_stock_reports.setRange(1, 10000)
        self.max_stock_reports.setValue(self._config.max_llm_stock_reports)
        form.addRow("Max stored stock reports", self.max_stock_reports)

        self.queue_enabled = QCheckBox("Enable LLM report queue")
        self.queue_enabled.setChecked(self._config.llm_report_queue_enabled)
        form.addRow("Report queue", self.queue_enabled)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_config(self) -> ScreeningReportConfig:
        max_speed = self.max_samples.value()
        min_speed = min(self.min_samples.value(), max_speed)
        return ScreeningReportConfig(
            auto_llm_reports=self._config.auto_llm_reports,
            telegram_after_llm_reports=self._config.telegram_after_llm_reports,
            report_output_dir=self._config.report_output_dir,
            max_llm_report_stocks=self.max_report_stocks.value(),
            max_llm_stock_reports=self.max_stock_reports.value(),
            send_summary_to_telegram=self._config.send_summary_to_telegram,
            telegram_send_as_text=self._config.telegram_send_as_text,
            max_samples_per_second=max_speed,
            adaptive_speed_down=self.adaptive_speed_down.isChecked(),
            min_samples_per_second=min_speed,
            llm_report_queue_enabled=self.queue_enabled.isChecked(),
            llm_report_interval_minutes=self.llm_report_interval.value(),
            scheduled_screening_enabled=self._config.scheduled_screening_enabled,
            scheduled_screening_interval_minutes=self.scheduled_interval.value(),
        )
