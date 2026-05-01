from __future__ import annotations

from pathlib import Path

import yaml

from market_viewer.models import LLMConfig, TelegramConfig


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


def save_app_configs(llm_config: LLMConfig, telegram_config: TelegramConfig) -> None:
    payload = {
        "llm": {
            "base_url": llm_config.base_url,
            "api_key": llm_config.api_key,
            "model": llm_config.model,
            "temperature": llm_config.temperature,
            "max_tokens": llm_config.max_tokens,
            "timeout_seconds": llm_config.timeout_seconds,
        },
        "telegram": {
            "bot_token": telegram_config.bot_token,
            "chat_id": telegram_config.chat_id,
        },
    }
    _save_raw_config(payload)
