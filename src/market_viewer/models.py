from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MarketDefinition:
    id: str
    label: str
    country: str
    currency: str
    listing_sources: tuple[str, ...]


@dataclass(slots=True)
class StockReference:
    code: str
    name: str
    market: str
    country: str
    currency: str

    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.code}, {self.market})"


@dataclass(slots=True)
class LLMConfig:
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4.1-mini"
    temperature: float = 0.2
    max_tokens: int = 12000
    timeout_seconds: int = 90

    @property
    def connection_ready(self) -> bool:
        return bool(self.base_url.strip() and self.api_key.strip() and self.model.strip())


@dataclass(slots=True)
class TelegramConfig:
    bot_token: str = ""
    chat_id: str = ""

    @property
    def connection_ready(self) -> bool:
        return bool(self.bot_token.strip() and self.chat_id.strip())


@dataclass(slots=True)
class ScreeningReportConfig:
    auto_llm_reports: bool = False
    telegram_after_llm_reports: bool = True
    report_output_dir: str = "log"
    max_llm_report_stocks: int = 30
    send_summary_to_telegram: bool = True
    telegram_send_as_text: bool = True


@dataclass(slots=True)
class KiwoomConfig:
    enabled: bool = False
    mock: bool = False
    base_url: str = "https://api.kiwoom.com"
    mock_base_url: str = "https://mockapi.kiwoom.com"
    websocket_url: str = "wss://api.kiwoom.com:10000"
    mock_websocket_url: str = "wss://mockapi.kiwoom.com:10000"
    appkey: str = ""
    secretkey: str = ""
    token_cache_enabled: bool = True

    @property
    def rest_base_url(self) -> str:
        return self.mock_base_url if self.mock else self.base_url

    @property
    def active_websocket_url(self) -> str:
        return self.mock_websocket_url if self.mock else self.websocket_url

    @property
    def connection_ready(self) -> bool:
        return bool(self.enabled and self.rest_base_url.strip() and self.appkey.strip() and self.secretkey.strip())


@dataclass(slots=True)
class FundamentalSnapshot:
    as_of_date: str = ""
    values: dict[str, float | int | str | None] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ReportRow:
    section: str
    label: str
    value: str
    note: str = ""


@dataclass(slots=True)
class PromptLayerDefinition:
    id: str
    name: str
    description: str
    system_text: str
    shortcut: str = ""


@dataclass(slots=True)
class AppSessionState:
    market_scope: str = "KOSPI"
    selected_stock: StockReference | None = None
    filter_prompt: str = ""
    user_request_text: str = ""
    active_prompt_layers: list[str] = field(
        default_factory=lambda: [
            "technical_analyst",
            "korean_output",
            "numeric_evidence",
            "response_contract",
            "fast_response",
            "direct_answer",
        ]
    )
    chart_preset: str = "1Y"
    chart_visible_start: str | None = None
    chart_visible_end: str | None = None
    chart_tab_index: int = 0
    splitter_sizes: list[int] = field(default_factory=lambda: [680, 500])
    llm_config: LLMConfig = field(default_factory=LLMConfig)
