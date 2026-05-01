from __future__ import annotations

from market_viewer.analysis.filter_models import FilterCondition


ALLOWED_MARKETS = {"KOSPI", "KOSDAQ", "TSE"}
ALLOWED_FIELDS = {
    "price_vs_ma",
    "RSI14",
    "VolumeRatio",
    "PER",
    "PBR",
    "EPS",
    "BPS",
    "DividendYield",
    "Return5D",
    "Return20D",
    "Return60D",
    "Return120D",
    "MACD_CROSS",
    "MACD_REL",
    "MA_ALIGNMENT",
    "NEW_HIGH",
}
ALLOWED_OPERATORS = {">", ">=", "<", "<=", "==", "="}
ALLOWED_NEW_HIGH_WINDOWS = {20, 60, 120}
ALLOWED_RETURN_FIELDS = {"Return5D", "Return20D", "Return60D", "Return120D"}
ALLOWED_PRICE_MA_WINDOWS = {5, 20, 60, 120}


def sanitize_markets(raw_markets: object) -> tuple[list[str], list[str]]:
    if not isinstance(raw_markets, list):
        return [], ["시장 정보가 배열 형식이 아니어서 무시했습니다."]
    markets: list[str] = []
    warnings: list[str] = []
    for item in raw_markets:
        market = str(item).strip().upper()
        if not market:
            continue
        if market in ALLOWED_MARKETS:
            markets.append(market)
        else:
            warnings.append(f"지원하지 않는 시장 '{market}'은 무시했습니다.")
    return list(dict.fromkeys(markets)), warnings


def sanitize_conditions(raw_conditions: object) -> tuple[list[FilterCondition], list[str]]:
    if not isinstance(raw_conditions, list):
        return [], ["조건 목록 형식이 잘못되어 무시했습니다."]

    conditions: list[FilterCondition] = []
    warnings: list[str] = []
    for item in raw_conditions:
        if not isinstance(item, dict):
            warnings.append("사전 형식이 아닌 조건을 무시했습니다.")
            continue
        field = str(item.get("field", "")).strip()
        operator = normalize_operator(item.get("operator"))
        value = item.get("value")
        label = str(item.get("label", "")).strip()

        if field not in ALLOWED_FIELDS:
            warnings.append(f"지원하지 않는 조건 필드 '{field}'은 무시했습니다.")
            continue
        if operator not in ALLOWED_OPERATORS:
            warnings.append(f"지원하지 않는 연산자 '{operator}'은 무시했습니다.")
            continue

        normalized_value = normalize_value(field, value)
        if normalized_value is None:
            warnings.append(f"{field} 조건의 값 '{value}'을 해석하지 못해 무시했습니다.")
            continue

        if operator == "=":
            operator = "=="
        conditions.append(
            FilterCondition(
                field=field,
                operator=operator,
                value=normalized_value,
                label=label or build_condition_label(field, operator, normalized_value),
            )
        )

    return deduplicate_conditions(conditions), warnings


def normalize_operator(raw_operator: object) -> str:
    operator = str(raw_operator).strip()
    if operator == "":
        return ""
    return "==" if operator == "=" else operator


def normalize_value(field: str, value: object) -> object | None:
    if field == "price_vs_ma":
        number = coerce_int(value)
        if number in ALLOWED_PRICE_MA_WINDOWS:
            return number
        return None
    if field == "RSI14":
        return coerce_float(value)
    if field == "VolumeRatio":
        return coerce_float(value)
    if field in {"PER", "PBR", "EPS", "BPS", "DividendYield"}:
        return coerce_float(value)
    if field in ALLOWED_RETURN_FIELDS:
        return coerce_float(value)
    if field == "MACD_CROSS":
        text = str(value).strip().lower()
        return text if text in {"golden", "dead"} else None
    if field == "MACD_REL":
        text = str(value).strip().lower()
        return "signal" if text == "signal" else None
    if field == "MA_ALIGNMENT":
        text = str(value).strip().lower()
        if text in {"bullish_5_20_60", "bearish_5_20_60"}:
            return text
        return None
    if field == "NEW_HIGH":
        number = coerce_int(value)
        if number in ALLOWED_NEW_HIGH_WINDOWS:
            return number
        return None
    return None


def coerce_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def coerce_int(value: object) -> int | None:
    number = coerce_float(value)
    if number is None:
        return None
    integer = int(number)
    if abs(number - integer) > 1e-9:
        return None
    return integer


def build_condition_label(field: str, operator: str, value: object) -> str:
    if field == "price_vs_ma":
        return f"종가 {operator} MA{value}"
    if field == "RSI14":
        return f"RSI14 {operator} {value:g}"
    if field == "VolumeRatio":
        return f"거래량 비율 {operator} {value:g}"
    if field in {"PER", "PBR", "EPS", "BPS", "DividendYield"}:
        label_map = {
            "PER": "PER",
            "PBR": "PBR",
            "EPS": "EPS",
            "BPS": "BPS",
            "DividendYield": "배당수익률",
        }
        return f"{label_map[field]} {operator} {value:g}"
    if field in ALLOWED_RETURN_FIELDS:
        return f"{field} {operator} {value:g}"
    if field == "MACD_CROSS":
        return "MACD 골든크로스" if value == "golden" else "MACD 데드크로스"
    if field == "MACD_REL":
        return f"MACD {operator} Signal"
    if field == "MA_ALIGNMENT":
        return "정배열(MA5 > MA20 > MA60)" if value == "bullish_5_20_60" else "역배열(MA5 < MA20 < MA60)"
    if field == "NEW_HIGH":
        return f"{value}일 신고가"
    return f"{field} {operator} {value}"


def deduplicate_conditions(conditions: list[FilterCondition]) -> list[FilterCondition]:
    unique: dict[tuple[str, str, str], FilterCondition] = {}
    for condition in conditions:
        key = (condition.field, condition.operator, str(condition.value))
        unique[key] = condition
    return list(unique.values())


def unique_non_empty(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value.strip()))
