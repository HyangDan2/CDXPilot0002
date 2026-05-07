from __future__ import annotations

from pathlib import Path

import yaml

from market_viewer.analysis.condition_parser import (
    default_screening_conditions,
    dump_screening_conditions,
    load_screening_conditions as parse_screening_conditions,
)
from market_viewer.analysis.filter_models import ScreeningCondition
from market_viewer.models import KiwoomConfig, LLMConfig, ScreeningReportConfig, TelegramConfig


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def app_config_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config.yaml"


def _load_raw_config() -> dict:
    path = app_config_path()
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_llm_config() -> LLMConfig:
    raw = _load_raw_config()
    llm_raw = raw.get("llm", {})
    return LLMConfig(
        base_url=str(llm_raw.get("base_url", "https://api.openai.com/v1")),
        api_key=str(llm_raw.get("api_key", "")),
        model=str(llm_raw.get("model", "gpt-4.1-mini")),
        temperature=float(llm_raw.get("temperature", 0.2)),
        max_tokens=int(llm_raw.get("max_tokens", 12000)),
        timeout_seconds=int(llm_raw.get("timeout_seconds", 90)),
    )


def load_telegram_config() -> TelegramConfig:
    raw = _load_raw_config()
    telegram_raw = raw.get("telegram", {})
    return TelegramConfig(
        bot_token=str(telegram_raw.get("bot_token", "")),
        chat_id=str(telegram_raw.get("chat_id", "")),
    )


def load_kiwoom_config() -> KiwoomConfig:
    raw = _load_raw_config()
    kiwoom_raw = raw.get("kiwoom", {})
    return KiwoomConfig(
        enabled=_as_bool(kiwoom_raw.get("enabled"), False),
        mock=_as_bool(kiwoom_raw.get("mock"), False),
        base_url=str(kiwoom_raw.get("base_url", "https://api.kiwoom.com")),
        mock_base_url=str(kiwoom_raw.get("mock_base_url", "https://mockapi.kiwoom.com")),
        websocket_url=str(kiwoom_raw.get("websocket_url", "wss://api.kiwoom.com:10000")),
        mock_websocket_url=str(kiwoom_raw.get("mock_websocket_url", "wss://mockapi.kiwoom.com:10000")),
        appkey=str(kiwoom_raw.get("appkey", "")),
        secretkey=str(kiwoom_raw.get("secretkey", "")),
        token_cache_enabled=_as_bool(kiwoom_raw.get("token_cache_enabled"), True),
    )


def load_screening_conditions() -> list[ScreeningCondition]:
    raw = _load_raw_config()
    screening_raw = raw.get("screening", {})
    conditions = parse_screening_conditions(screening_raw.get("custom_conditions"))
    return conditions or default_screening_conditions()


def load_screening_report_config() -> ScreeningReportConfig:
    raw = _load_raw_config()
    screening_raw = raw.get("screening", {})
    return ScreeningReportConfig(
        auto_llm_reports=_as_bool(screening_raw.get("auto_llm_reports"), False),
        telegram_after_llm_reports=_as_bool(screening_raw.get("telegram_after_llm_reports"), True),
        report_output_dir=str(screening_raw.get("report_output_dir", "log")),
        max_llm_report_stocks=max(1, int(screening_raw.get("max_llm_report_stocks", 100))),
        max_llm_stock_reports=max(1, int(screening_raw.get("max_llm_stock_reports", 100))),
        send_summary_to_telegram=_as_bool(screening_raw.get("send_summary_to_telegram"), True),
        telegram_send_as_text=_as_bool(screening_raw.get("telegram_send_as_text"), True),
        max_samples_per_second=max(0.1, float(screening_raw.get("max_samples_per_second", 10.0))),
        adaptive_speed_down=_as_bool(screening_raw.get("adaptive_speed_down"), True),
        min_samples_per_second=max(0.1, float(screening_raw.get("min_samples_per_second", 1.0))),
        llm_report_queue_enabled=_as_bool(screening_raw.get("llm_report_queue_enabled"), True),
        llm_report_interval_minutes=max(1, int(screening_raw.get("llm_report_interval_minutes", 5))),
        scheduled_screening_enabled=_as_bool(screening_raw.get("scheduled_screening_enabled"), False),
        scheduled_screening_interval_minutes=max(1, int(screening_raw.get("scheduled_screening_interval_minutes", 60))),
    )


def _save_raw_config(payload: dict) -> None:
    path = app_config_path()
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def save_llm_config(config: LLMConfig) -> None:
    raw = _load_raw_config()
    raw["llm"] = {
        "base_url": config.base_url,
        "api_key": config.api_key,
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "timeout_seconds": config.timeout_seconds,
    }
    _save_raw_config(raw)


def save_telegram_config(config: TelegramConfig) -> None:
    raw = _load_raw_config()
    raw["telegram"] = {
        "bot_token": config.bot_token,
        "chat_id": config.chat_id,
    }
    _save_raw_config(raw)


def save_kiwoom_config(config: KiwoomConfig) -> None:
    raw = _load_raw_config()
    raw["kiwoom"] = _kiwoom_payload(config)
    _save_raw_config(raw)


def save_screening_conditions(conditions: list[ScreeningCondition]) -> None:
    raw = _load_raw_config()
    raw.setdefault("screening", {})
    raw["screening"]["custom_conditions"] = dump_screening_conditions(conditions)
    raw["screening"]["active_conditions"] = [condition.name for condition in conditions if condition.active]
    _save_raw_config(raw)


def save_screening_report_config(config: ScreeningReportConfig) -> None:
    raw = _load_raw_config()
    raw.setdefault("screening", {})
    raw["screening"].update(_screening_report_payload(config))
    _save_raw_config(raw)


def save_app_configs(
    llm_config: LLMConfig,
    telegram_config: TelegramConfig,
    kiwoom_config: KiwoomConfig | None = None,
) -> None:
    payload = _load_raw_config()
    payload["llm"] = {
        "base_url": llm_config.base_url,
        "api_key": llm_config.api_key,
        "model": llm_config.model,
        "temperature": llm_config.temperature,
        "max_tokens": llm_config.max_tokens,
        "timeout_seconds": llm_config.timeout_seconds,
    }
    payload["telegram"] = {
        "bot_token": telegram_config.bot_token,
        "chat_id": telegram_config.chat_id,
    }
    if kiwoom_config is not None:
        payload["kiwoom"] = _kiwoom_payload(kiwoom_config)
    _save_raw_config(payload)


def _kiwoom_payload(config: KiwoomConfig) -> dict:
    return {
        "enabled": config.enabled,
        "mock": config.mock,
        "base_url": config.base_url,
        "mock_base_url": config.mock_base_url,
        "websocket_url": config.websocket_url,
        "mock_websocket_url": config.mock_websocket_url,
        "appkey": config.appkey,
        "secretkey": config.secretkey,
        "token_cache_enabled": config.token_cache_enabled,
    }


def _screening_report_payload(config: ScreeningReportConfig) -> dict:
    return {
        "auto_llm_reports": config.auto_llm_reports,
        "telegram_after_llm_reports": config.telegram_after_llm_reports,
        "report_output_dir": config.report_output_dir,
        "max_llm_report_stocks": config.max_llm_report_stocks,
        "max_llm_stock_reports": config.max_llm_stock_reports,
        "send_summary_to_telegram": config.send_summary_to_telegram,
        "telegram_send_as_text": config.telegram_send_as_text,
        "max_samples_per_second": config.max_samples_per_second,
        "adaptive_speed_down": config.adaptive_speed_down,
        "min_samples_per_second": config.min_samples_per_second,
        "llm_report_queue_enabled": config.llm_report_queue_enabled,
        "llm_report_interval_minutes": config.llm_report_interval_minutes,
        "scheduled_screening_enabled": config.scheduled_screening_enabled,
        "scheduled_screening_interval_minutes": config.scheduled_screening_interval_minutes,
    }
