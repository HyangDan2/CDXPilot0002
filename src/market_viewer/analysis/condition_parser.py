from __future__ import annotations

from market_viewer.analysis.filter_models import ScreeningCondition, ScreeningMetricRule


METRIC_DEFINITIONS: list[tuple[str, str]] = [
    ("PER", "PER"),
    ("PBR", "PBR"),
    ("ROE", "ROE"),
    ("EPS", "EPS"),
    ("BPS", "BPS"),
    ("매출액", "Revenue"),
    ("영업이익", "OperatingProfit"),
    ("순이익", "NetIncome"),
    ("시가총액", "MarketCap"),
    ("외인비율", "ForeignOwnershipRatio"),
    ("거래량", "Volume"),
    ("거래량MA20", "VolumeMA20"),
    ("거래량배율", "VolumeRatio"),
]


def default_screening_conditions() -> list[ScreeningCondition]:
    return [
        ScreeningCondition(
            name="bullish_value",
            operand="AND",
            ma_order=[5, 20, 60],
            metrics=[
                ScreeningMetricRule("PER", "<", 5.0),
                ScreeningMetricRule("PBR", "<", 0.5),
                ScreeningMetricRule("ROE", ">", 10.0),
                ScreeningMetricRule("OperatingProfit", ">", 0.0),
                ScreeningMetricRule("NetIncome", ">", 0.0),
            ],
        ),
        ScreeningCondition(name="ma5_above_ma120", operand="AND", ma_above=[[5, 120]]),
        ScreeningCondition(
            name="volume_spike_value",
            operand="AND",
            ma_order=[5, 20],
            metrics=[
                ScreeningMetricRule("VolumeRatio", ">", 2.0),
                ScreeningMetricRule("VolumeRatio", "<", 10.0),
                ScreeningMetricRule("Volume", ">", 1_000_000.0),
                ScreeningMetricRule("PER", "<", 10.0),
                ScreeningMetricRule("PBR", "<", 1.0),
            ],
        ),
        ScreeningCondition(
            name="foreign_or_value",
            operand="OR",
            metrics=[
                ScreeningMetricRule("ForeignOwnershipRatio", ">", 20.0),
                ScreeningMetricRule("ROE", ">", 10.0),
                ScreeningMetricRule("PBR", "<", 0.5),
            ],
        ),
    ]


def parse_ma_order(text: str) -> list[int]:
    text = (text or "").strip()
    if not text:
        return []
    try:
        parts = [int(chunk.strip().lower().replace("ma", "")) for chunk in text.split(">") if chunk.strip()]
    except ValueError as exc:
        raise ValueError(f"Invalid MA Order: {text}. Example: 5>20>60") from exc
    if len(parts) < 2:
        raise ValueError(f"Invalid MA Order: {text}. Example: 5>20>60")
    return parts


def format_ma_order(values: list[int]) -> str:
    return ">".join(str(value) for value in values)


def parse_ma_above(text: str) -> list[list[int]]:
    text = (text or "").strip()
    if not text:
        return []
    pairs: list[list[int]] = []
    try:
        for chunk in text.split(","):
            if not chunk.strip():
                continue
            left, right = chunk.split(">")
            pairs.append([int(left.strip().lower().replace("ma", "")), int(right.strip().lower().replace("ma", ""))])
    except ValueError as exc:
        raise ValueError(f"Invalid MA Above: {text}. Example: 5>120") from exc
    return pairs


def format_ma_above(values: list[list[int]]) -> str:
    return ",".join(f"{pair[0]}>{pair[1]}" for pair in values if len(pair) == 2)


def parse_metric_rules(metric: str, text: str) -> list[ScreeningMetricRule]:
    text = (text or "").strip()
    if not text:
        return []
    return [parse_single_metric_rule(metric, chunk.strip()) for chunk in text.split(",") if chunk.strip()]


def parse_single_metric_rule(metric: str, text: str) -> ScreeningMetricRule:
    for op in [">=", "<=", "!=", "==", ">", "<", "="]:
        if text.startswith(op):
            value_text = text[len(op) :].strip()
            normalized_op = "==" if op == "=" else op
            break
    else:
        normalized_op = "<"
        value_text = text
    try:
        value = float(value_text.replace(",", ""))
    except ValueError as exc:
        raise ValueError(f"Invalid metric rule for {metric}: {text}. Example: <5 or >2,<10") from exc
    return ScreeningMetricRule(metric=metric, op=normalized_op, value=value)


def dump_screening_conditions(conditions: list[ScreeningCondition]) -> list[dict]:
    return [
        {
            "name": condition.name,
            "enabled": condition.enabled,
            "operand": condition.operand.upper(),
            "ma_order": condition.ma_order,
            "ma_above": condition.ma_above,
            "metrics": [
                {"metric": rule.metric, "op": rule.op, "value": rule.value}
                for rule in condition.metrics
            ],
        }
        for condition in conditions
    ]


def load_screening_conditions(raw_conditions: object) -> list[ScreeningCondition]:
    if not isinstance(raw_conditions, list):
        return []
    loaded: list[ScreeningCondition] = []
    for item in raw_conditions:
        if not isinstance(item, dict):
            continue
        metrics: list[ScreeningMetricRule] = []
        for rule in item.get("metrics", []):
            if not isinstance(rule, dict):
                continue
            try:
                metrics.append(
                    ScreeningMetricRule(
                        metric=str(rule.get("metric", "")),
                        op=str(rule.get("op", "<")),
                        value=float(rule.get("value", 0.0)),
                    )
                )
            except (TypeError, ValueError):
                continue
        loaded.append(
            ScreeningCondition(
                name=str(item.get("name", "")),
                enabled=bool(item.get("enabled", True)),
                operand=str(item.get("operand", "AND")).upper(),
                ma_order=[int(value) for value in item.get("ma_order", [])],
                ma_above=[
                    [int(pair[0]), int(pair[1])]
                    for pair in item.get("ma_above", [])
                    if isinstance(pair, (list, tuple)) and len(pair) == 2
                ],
                metrics=metrics,
            )
        )
    return loaded


def summarize_conditions(conditions: list[ScreeningCondition]) -> str:
    active = [condition for condition in conditions if condition.active]
    if not active:
        return "조건 없음"
    return " / ".join(condition.label for condition in active)
