from __future__ import annotations

import time

import pandas as pd

from market_viewer.analysis.condition_evaluator import (
    conditions_require_fundamentals,
    conditions_require_price,
    row_matches_custom_conditions,
)
from market_viewer.analysis.filter_models import FilterCondition, ParsedFilter
from market_viewer.analysis.indicators import add_indicators
from market_viewer.data.market_service import MarketService
from market_viewer.services.rate_limiter import AdaptiveRateLimiter

FUNDAMENTAL_FIELDS = {
    "PER",
    "PBR",
    "ROE",
    "EPS",
    "BPS",
    "Revenue",
    "OperatingProfit",
    "NetIncome",
    "MarketCap",
    "ForeignOwnershipRatio",
}


def screen_listing(
    market_service: MarketService,
    listing: pd.DataFrame,
    parsed_filter: ParsedFilter,
    months: int = 12,
    progress_callback=None,
    cancel_checker=None,
    rate_limiter: AdaptiveRateLimiter | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    working = listing.copy()
    warnings = list(parsed_filter.warnings)

    if parsed_filter.markets:
        working = working[working["Market"].isin(parsed_filter.markets)]

    if not parsed_filter.conditions and not parsed_filter.custom_conditions:
        return working.reset_index(drop=True), warnings

    matched_rows: list[pd.Series] = []
    failures = 0
    total = len(working)
    started_at = time.monotonic()
    stopped = False
    needs_price = bool(parsed_filter.conditions) or conditions_require_price(parsed_filter.custom_conditions)
    needs_fundamentals = (
        any(condition.field in FUNDAMENTAL_FIELDS for condition in parsed_filter.conditions)
        or conditions_require_fundamentals(parsed_filter.custom_conditions)
    )

    for done, (_, row) in enumerate(working.iterrows(), start=1):
        if rate_limiter is not None:
            rate_limiter.wait()
        if cancel_checker is not None and cancel_checker():
            stopped = True
            _emit_progress(progress_callback, done - 1, total, len(matched_rows), failures, row, started_at, rate_limiter=rate_limiter, stopped=True)
            break
        stock = market_service.build_stock_reference(row)
        try:
            frame = None
            latest = None
            if needs_price:
                frame = add_indicators(market_service.load_price_history(stock, months=months))
                latest = frame.iloc[-1] if not frame.empty else None
            fundamentals = {}
            if needs_fundamentals:
                fundamentals = market_service.load_fundamental_snapshot(stock).values
            legacy_match = True
            if parsed_filter.conditions:
                if frame is None:
                    legacy_match = False
                else:
                    legacy_match = _matches_conditions(frame, row, parsed_filter.conditions, fundamentals)
            custom_match = row_matches_custom_conditions(parsed_filter.custom_conditions, latest, fundamentals)
            if legacy_match and custom_match:
                enriched_row = row.copy()
                if latest is not None:
                    for field in ["MA20", "MA60", "RSI14", "MACD", "VolumeRatio", "Return20D", "VolumeMA20"]:
                        if field in latest:
                            enriched_row[field] = latest[field]
                for field, value in fundamentals.items():
                    if field in FUNDAMENTAL_FIELDS:
                        enriched_row[field] = value
                matched_rows.append(enriched_row)
            if rate_limiter is not None:
                rate_limiter.record_success()
        except Exception as exc:
            if rate_limiter is not None:
                rate_limiter.record_error(exc)
            failures += 1
            if failures <= 3:
                warnings.append(f"{stock.display_name} 스크리닝 실패: {exc}")
        _emit_progress(progress_callback, done, total, len(matched_rows), failures, row, started_at, rate_limiter=rate_limiter)

    if failures > 3:
        warnings.append(f"추가 실패 종목 {failures - 3}건은 로그를 생략했습니다.")

    if matched_rows:
        result = pd.DataFrame(matched_rows).sort_values(["Market", "Name"]).reset_index(drop=True)
    else:
        # Preserve the original listing schema so the UI can safely render a valid 0-row result.
        result = working.head(0).copy().reset_index(drop=True)
    if stopped:
        warnings.append("사용자 요청으로 스크리닝을 중지했습니다. 현재까지 매칭된 결과만 표시합니다.")
    return result, warnings


def _emit_progress(
    progress_callback,
    done: int,
    total: int,
    matched: int,
    failures: int,
    row: pd.Series,
    started_at: float,
    rate_limiter: AdaptiveRateLimiter | None = None,
    stopped: bool = False,
) -> None:
    if progress_callback is None:
        return
    from market_viewer.analysis.filter_models import ScreeningProgress

    progress_callback(
        ScreeningProgress(
            done=done,
            total=total,
            matched=matched,
            failures=failures,
            current_code=str(row.get("Code", "")),
            current_name=str(row.get("Name", "")),
            elapsed_seconds=time.monotonic() - started_at,
            stopped=stopped,
            samples_per_second=rate_limiter.current_samples_per_second if rate_limiter is not None else 0.0,
            adaptive_slowdown=rate_limiter.adaptive_slowdown if rate_limiter is not None else False,
        )
    )


def _matches_conditions(
    frame: pd.DataFrame,
    listing_row: pd.Series,
    conditions: list[FilterCondition],
    fundamentals: dict[str, object] | None = None,
) -> bool:
    if frame.empty:
        return False
    latest = frame.iloc[-1]
    previous = frame.iloc[-2] if len(frame) > 1 else latest
    fundamentals = fundamentals or {}

    for condition in conditions:
        if condition.field in FUNDAMENTAL_FIELDS:
            field_value = fundamentals.get(condition.field)
            if field_value is None or pd.isna(field_value):
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

        if condition.field == "MA_CROSS":
            left_window, right_window = {
                "golden_5_20": (5, 20),
                "golden_20_60": (20, 60),
                "golden_20_224": (20, 224),
                "golden_60_224": (60, 224),
            }.get(str(condition.value), (0, 0))
            if not left_window or not right_window:
                return False
            prev_left = previous.get(f"MA{left_window}")
            prev_right = previous.get(f"MA{right_window}")
            curr_left = latest.get(f"MA{left_window}")
            curr_right = latest.get(f"MA{right_window}")
            if any(pd.isna(value) for value in [prev_left, prev_right, curr_left, curr_right]):
                return False
            if not (prev_left <= prev_right and curr_left > curr_right):
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
