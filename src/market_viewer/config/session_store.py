from __future__ import annotations

from pathlib import Path

import yaml

from market_viewer.models import AppSessionState, LLMConfig, StockReference


def save_session(path: str, state: AppSessionState) -> None:
    payload = {
        "version": 1,
        "market_scope": state.market_scope,
        "selected_stock": _dump_stock(state.selected_stock),
        "filter_prompt": state.filter_prompt,
        "user_request_text": state.user_request_text,
        "active_prompt_layers": state.active_prompt_layers,
        "chart": {
            "preset": state.chart_preset,
            "visible_start": state.chart_visible_start,
            "visible_end": state.chart_visible_end,
            "tab_index": state.chart_tab_index,
        },
        "layout": {"splitter_sizes": state.splitter_sizes},
    }
    Path(path).write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_session(path: str) -> AppSessionState:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    chart_raw = raw.get("chart", {})
    layout_raw = raw.get("layout", {})
    return AppSessionState(
        market_scope=str(raw.get("market_scope", "KOSPI")),
        selected_stock=_load_stock(raw.get("selected_stock")),
        filter_prompt=str(raw.get("filter_prompt", "")),
        user_request_text=str(raw.get("user_request_text", "")),
        active_prompt_layers=list(raw.get("active_prompt_layers", []))
        or ["technical_analyst", "korean_output", "numeric_evidence"],
        chart_preset=str(chart_raw.get("preset", "1Y")),
        chart_visible_start=chart_raw.get("visible_start"),
        chart_visible_end=chart_raw.get("visible_end"),
        chart_tab_index=int(chart_raw.get("tab_index", 0)),
        splitter_sizes=list(layout_raw.get("splitter_sizes", [360, 760, 460])),
        llm_config=LLMConfig(),
    )


def _dump_stock(stock: StockReference | None) -> dict[str, str] | None:
    if stock is None:
        return None
    return {
        "code": stock.code,
        "name": stock.name,
        "market": stock.market,
        "country": stock.country,
        "currency": stock.currency,
    }


def _load_stock(raw: dict[str, str] | None) -> StockReference | None:
    if not raw:
        return None
    return StockReference(
        code=str(raw.get("code", "")),
        name=str(raw.get("name", "")),
        market=str(raw.get("market", "")),
        country=str(raw.get("country", "")),
        currency=str(raw.get("currency", "")),
    )
