from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from market_viewer.models import LLMConfig


class LLMSettingsDialog(QDialog):
    def __init__(self, config: LLMConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("LLM 연결 설정")
        self._setup_ui(config)

    def _setup_ui(self, config: LLMConfig) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.base_url_edit = QLineEdit(config.base_url)
        self.api_key_edit = QLineEdit(config.api_key)
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.model_edit = QLineEdit(config.model)

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(config.temperature)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(128, 64000)
        self.max_tokens_spin.setValue(config.max_tokens)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 300)
        self.timeout_spin.setValue(config.timeout_seconds)

        form.addRow("Base URL", self.base_url_edit)
        form.addRow("API Key", self.api_key_edit)
        form.addRow("Model", self.model_edit)
        form.addRow("Temperature", self.temperature_spin)
        form.addRow("Max Tokens", self.max_tokens_spin)
        form.addRow("Timeout (s)", self.timeout_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_config(self) -> LLMConfig:
        return LLMConfig(
            base_url=self.base_url_edit.text().strip(),
            api_key=self.api_key_edit.text().strip(),
            model=self.model_edit.text().strip(),
            temperature=self.temperature_spin.value(),
            max_tokens=self.max_tokens_spin.value(),
            timeout_seconds=self.timeout_spin.value(),
        )
