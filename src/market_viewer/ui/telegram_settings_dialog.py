from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QVBoxLayout

from market_viewer.models import TelegramConfig


class TelegramSettingsDialog(QDialog):
    def __init__(self, config: TelegramConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Telegram 설정")
        self._setup_ui(config)

    def _setup_ui(self, config: TelegramConfig) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.bot_token_edit = QLineEdit(config.bot_token)
        self.bot_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.chat_id_edit = QLineEdit(config.chat_id)

        form.addRow("Bot Token", self.bot_token_edit)
        form.addRow("Chat ID", self.chat_id_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_config(self) -> TelegramConfig:
        return TelegramConfig(
            bot_token=self.bot_token_edit.text().strip(),
            chat_id=self.chat_id_edit.text().strip(),
        )
