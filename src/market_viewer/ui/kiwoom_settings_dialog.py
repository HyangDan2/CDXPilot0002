from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)

from market_viewer.models import KiwoomConfig


class KiwoomSettingsDialog(QDialog):
    def __init__(self, config: KiwoomConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Kiwoom REST 설정")
        self.resize(620, 420)
        self._setup_ui(config)

    def _setup_ui(self, config: KiwoomConfig) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.enabled_check = QCheckBox("Kiwoom REST backend 사용")
        self.enabled_check.setChecked(config.enabled)
        self.mock_check = QCheckBox("모의투자 도메인 사용")
        self.mock_check.setChecked(config.mock)
        self.base_url_edit = QLineEdit(config.base_url)
        self.mock_base_url_edit = QLineEdit(config.mock_base_url)
        self.websocket_url_edit = QLineEdit(config.websocket_url)
        self.mock_websocket_url_edit = QLineEdit(config.mock_websocket_url)
        self.appkey_edit = QLineEdit(config.appkey)
        self.secretkey_edit = QLineEdit(config.secretkey)
        self.secretkey_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_cache_check = QCheckBox("토큰 캐시 사용")
        self.token_cache_check.setChecked(config.token_cache_enabled)

        form.addRow("", self.enabled_check)
        form.addRow("", self.mock_check)
        form.addRow("운영 REST URL", self.base_url_edit)
        form.addRow("모의 REST URL", self.mock_base_url_edit)
        form.addRow("운영 WebSocket URL", self.websocket_url_edit)
        form.addRow("모의 WebSocket URL", self.mock_websocket_url_edit)
        form.addRow("App Key", self.appkey_edit)
        form.addRow("Secret Key", self.secretkey_edit)
        form.addRow("", self.token_cache_check)
        layout.addLayout(form)

        guidance = QTextEdit()
        guidance.setReadOnly(True)
        guidance.setFixedHeight(86)
        guidance.setPlainText(
            "config.yaml에는 실제 appkey/secretkey를 저장하고, config.example.yaml에는 빈 형식만 둡니다.\n"
            "토큰은 au10001로 발급받아 런타임 메모리에 보관하며, 설정 파일에는 저장하지 않습니다.\n"
            "현재 데이터 backend는 ka10099, ka10081, ka10001을 사용합니다."
        )
        layout.addWidget(guidance)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_config(self) -> KiwoomConfig:
        return KiwoomConfig(
            enabled=self.enabled_check.isChecked(),
            mock=self.mock_check.isChecked(),
            base_url=self.base_url_edit.text().strip(),
            mock_base_url=self.mock_base_url_edit.text().strip(),
            websocket_url=self.websocket_url_edit.text().strip(),
            mock_websocket_url=self.mock_websocket_url_edit.text().strip(),
            appkey=self.appkey_edit.text().strip(),
            secretkey=self.secretkey_edit.text().strip(),
            token_cache_enabled=self.token_cache_check.isChecked(),
        )
