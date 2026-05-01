from __future__ import annotations

import pandas as pd

from market_viewer.analysis.filter_models import FilterCondition, ParsedFilter
from market_viewer.analysis.indicators import add_indicators
from market_viewer.data.market_service import MarketService


def screen_listing(
    market_service: MarketService,
    listing: pd.DataFrame,
    parsed_filter: ParsedFilter,
    months: int = 12,
) -> tuple[pd.DataFrame, list[str]]:
    working = listing.copy()
    warnings = list(parsed_filter.warnings)

    if parsed_filter.markets:
        working = working[working["Market"].isin(parsed_filter.markets)]

    if not parsed_filter.conditions:
        return working.reset_index(drop=True), warnings

    matched_rows: list[pd.Series] = []
    failures = 0

    for _, row in working.iterrows():
        stock = market_service.build_stock_reference(row)
        try:
            frame = add_indicators(market_service.load_price_history(stock, months=months))
            if _matches_conditions(frame, row, parsed_filter.conditions):
                latest = frame.iloc[-1]
                enriched_row = row.copy()
                for field in ["MA20", "MA60", "RSI14", "MACD", "VolumeRatio", "Return20D"]:
                    if field in latest:
                        enriched_row[field] = latest[field]
                matched_rows.append(enriched_row)
        except Exception as exc:
            failures += 1
            if failures <= 3:
                warnings.append(f"{stock.display_name} 스크리닝 실패: {exc}")

    if failures > 3:
        warnings.append(f"추가 실패 종목 {failures - 3}건은 로그를 생략했습니다.")

    if matched_rows:
        result = pd.DataFrame(matched_rows).sort_values(["Market", "Name"]).reset_index(drop=True)
    else:
        # Preserve the original listing schema so the UI can safely render a valid 0-row result.
        result = working.head(0).copy().reset_index(drop=True)
    return result, warnings


def _matches_conditions(frame: pd.DataFrame, listing_row: pd.Series, conditions: list[FilterCondition]) -> bool:
    if frame.empty:
        return False
    latest = frame.iloc[-1]
    previous = frame.iloc[-2] if len(frame) > 1 else latest

    for condition in conditions:
        if condition.field in {"PER", "PBR", "EPS", "BPS", "DividendYield"}:
            field_value = listing_row.get(condition.field)
            if pd.isna(field_value):
                return False
            if not _compare(float(field_value), condition.operator, float(condition.value)):
                return False
            continue

        if condition.field == "price_vs_ma":
            moving_average = latest.get(f"MA{int(condition.value)}")
            if pd.isna(moving_average):
                return False
            if condition.operator == ">" and not float(latest["Close"]) > float(moving_average):
                return False
            if condition.operator == "<" and not float(latest["Close"]) < float(moving_average):
                return False
            continue

        if condition.field == "MACD_CROSS":
            prev_macd = previous.get("MACD")
            prev_signal = previous.get("MACDSignal")
            curr_macd = latest.get("MACD")
            curr_signal = latest.get("MACDSignal")
            if any(pd.isna(value) for value in [prev_macd, prev_signal, curr_macd, curr_signal]):
                return False
            if condition.value == "golden" and not (prev_macd <= prev_signal and curr_macd > curr_signal):
                return False
            if condition.value == "dead" and not (prev_macd >= prev_signal and curr_macd < curr_signal):
                return False
            continue

        if condition.field == "MACD_REL":
            curr_macd = latest.get("MACD")
            curr_signal = latest.get("MACDSignal")
            if any(pd.isna(value) for value in [curr_macd, curr_signal]):
                return False
            if condition.operator == ">" and not curr_macd > curr_signal:
                return False
            if condition.operator == "<" and not curr_macd < curr_signal:
                return False
            continue

        if condition.field == "MA_ALIGNMENT":
            ma5 = latest.get("MA5")
            ma20 = latest.get("MA20")
            ma60 = latest.get("MA60")
            if any(pd.isna(value) for value in [ma5, ma20, ma60]):
                return False
            if condition.value == "bullish_5_20_60" and not (ma5 > ma20 > ma60):
                return False
            if condition.value == "bearish_5_20_60" and not (ma5 < ma20 < ma60):
                return False
            continue

        if condition.field == "NEW_HIGH":
            window = int(condition.value)
            high_value = latest.get(f"High{window}D")
            current_high = latest.get("High")
            if any(pd.isna(value) for value in [high_value, current_high]):
                return False
            if not float(current_high) >= float(high_value):
                return False
            continue

        field_value = latest.get(condition.field)
        if pd.isna(field_value):
            return False
        if not _compare(float(field_value), condition.operator, float(condition.value)):
            return False
    return True


def _compare(left: float, operator: str, right: float) -> bool:
    if operator == ">":
        return left > right
    if operator == ">=":
        return left >= right
    if operator == "<":
        return left < right
    if operator == "<=":
        return left <= right
    if operator == "=" or operator == "==":
        return left == right
    return False
