from __future__ import annotations

import pandas as pd

from market_viewer.analysis.filter_models import ScreeningCondition


FUNDAMENTAL_METRICS = {
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

PRICE_METRICS = {"Volume", "VolumeMA20", "VolumeRatio"}


def condition_requires_price(condition: ScreeningCondition) -> bool:
    if condition.ma_order or condition.ma_above:
        return True
    return any(rule.metric in PRICE_METRICS or rule.metric.startswith("MA") for rule in condition.metrics)


def condition_requires_fundamentals(condition: ScreeningCondition) -> bool:
    return any(rule.metric in FUNDAMENTAL_METRICS for rule in condition.metrics)


def conditions_require_price(conditions: list[ScreeningCondition]) -> bool:
    return any(condition_requires_price(condition) for condition in conditions if condition.active)


def conditions_require_fundamentals(conditions: list[ScreeningCondition]) -> bool:
    return any(condition_requires_fundamentals(condition) for condition in conditions if condition.active)


def evaluate_custom_conditions(
    conditions: list[ScreeningCondition],
    latest: pd.Series | None,
    fundamentals: dict[str, object] | None,
) -> dict[str, bool]:
    results: dict[str, bool] = {}
    fundamentals = fundamentals or {}
    for condition in conditions:
        if not condition.name.strip():
            continue
        if not condition.enabled:
            results[condition.name] = False
            continue
        rule_results: list[bool] = []
        if condition.ma_order:
            rule_results.append(_eval_ma_order(latest, condition.ma_order))
        for pair in condition.ma_above:
            if len(pair) != 2:
                rule_results.append(False)
                continue
            rule_results.append(_safe_gt(_metric_value(f"MA{pair[0]}", latest, fundamentals), _metric_value(f"MA{pair[1]}", latest, fundamentals)))
        for rule in condition.metrics:
            rule_results.append(_compare_metric(rule.metric, rule.op, rule.value, latest, fundamentals))
        results[condition.name] = _combine(rule_results, condition.operand)
    return results


def row_matches_custom_conditions(
    conditions: list[ScreeningCondition],
    latest: pd.Series | None,
    fundamentals: dict[str, object] | None,
) -> bool:
    results = evaluate_custom_conditions(conditions, latest, fundamentals)
    return any(results.values()) if results else True


def _eval_ma_order(latest: pd.Series | None, order: list[int]) -> bool:
    if latest is None or len(order) < 2:
        return False
    values = [_metric_value(f"MA{window}", latest, {}) for window in order]
    return all(_safe_gt(values[index], values[index + 1]) for index in range(len(values) - 1))


def _metric_value(metric: str, latest: pd.Series | None, fundamentals: dict[str, object]) -> float | None:
    if metric in FUNDAMENTAL_METRICS:
        return _to_float(fundamentals.get(metric))
    if latest is None:
        return None
    if metric == "Volume":
        return _to_float(latest.get("Volume"))
    if metric == "VolumeMA20":
        return _to_float(latest.get("VolumeMA20"))
    if metric == "VolumeRatio":
        return _to_float(latest.get("VolumeRatio"))
    return _to_float(latest.get(metric))


def _compare_metric(metric: str, op: str, threshold: float, latest: pd.Series | None, fundamentals: dict[str, object]) -> bool:
    value = _metric_value(metric, latest, fundamentals)
    if value is None:
        return False
    return _compare(value, op, threshold)


def _compare(left: float, op: str, right: float) -> bool:
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op in {"=", "=="}:
        return left == right
    if op == "!=":
        return left != right
    return False


def _combine(results: list[bool], operand: str) -> bool:
    if not results:
        return True
    if operand.upper() == "OR":
        return any(results)
    return all(results)


def _safe_gt(left: float | None, right: float | None) -> bool:
    return left is not None and right is not None and left > right


def _to_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
