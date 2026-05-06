from __future__ import annotations

import pandas as pd

from market_viewer.analysis.filter_models import ParsedFilter
from market_viewer.analysis.filter_parser import parse_filter_prompt
from market_viewer.analysis.stock_screener import screen_listing
from market_viewer.data.market_service import MarketService


def parse_local_screening_prompt(prompt: str, market_scope: str) -> ParsedFilter:
    return parse_filter_prompt(prompt, market_scope)


def execute_screening(
    *,
    market_service: MarketService,
    market_scope: str,
    parsed_filter: ParsedFilter,
    listing: pd.DataFrame | None = None,
    progress_callback=None,
    cancel_checker=None,
) -> tuple[pd.DataFrame, list[str]]:
    source_listing = listing.copy() if listing is not None and not listing.empty else market_service.load_listing(market_scope)
    return screen_listing(
        market_service,
        source_listing,
        parsed_filter,
        progress_callback=progress_callback,
        cancel_checker=cancel_checker,
    )


def build_resolved_filter_markdown(parsed: ParsedFilter, market_scope: str) -> str:
    if not parsed.original_prompt.strip():
        return f"""## 해석 결과

- 기본 시장 범위: {market_scope}
- 조건 없음: 현재 시장 전체를 표시합니다.
"""

    markets = ", ".join(parsed.markets) if parsed.markets else market_scope
    conditions = parsed.conditions or []
    custom_conditions = parsed.custom_conditions or []
    if custom_conditions:
        condition_lines = "\n".join(f"- {condition.label}" for condition in custom_conditions if condition.active)
    else:
        condition_lines = "\n".join(f"- {condition.label}" for condition in conditions) if conditions else "- 해석된 조건 없음"
    warnings = "\n".join(f"- {warning}" for warning in parsed.warnings) if parsed.warnings else "- 없음"
    return f"""## 해석 결과

- 해석 소스: 메뉴 조건
- 시장 범위: {markets}
- 정규화 쿼리: {parsed.normalized_prompt or parsed.original_prompt}

### 적용 조건
{condition_lines}

### 경고
{warnings}
"""
