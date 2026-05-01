from __future__ import annotations

import re

from market_viewer.analysis.filter_models import FilterCondition, ParsedFilter


MARKET_ALIASES = {
    "KOSPI": ["코스피", "kospi"],
    "KOSDAQ": ["코스닥", "kosdaq"],
    "TSE": ["일본", "도쿄", "tse", "japan", "tokyo"],
    "KRX_ALL": ["krx", "한국시장", "국내시장"],
    "ALL": ["all", "전체시장"],
}

SUPPORTED_RETURN_WINDOWS = {5, 20, 60, 120}
SUPPORTED_HIGH_WINDOWS = {20, 60, 120}


def parse_filter_prompt(prompt: str, default_market_scope: str) -> ParsedFilter:
    normalized = prompt.strip()
    if not normalized:
        return ParsedFilter(original_prompt="", normalized_prompt="")

    lower = normalized.lower()
    markets = _extract_markets(lower)
    conditions: list[FilterCondition] = []
    warnings: list[str] = []

    _parse_moving_average_conditions(normalized, lower, conditions)
    _parse_rsi_conditions(normalized, lower, conditions)
    _parse_volume_conditions(normalized, lower, conditions)
    _parse_fundamental_conditions(normalized, lower, conditions)
    _parse_return_conditions(normalized, lower, conditions, warnings)
    _parse_macd_conditions(normalized, lower, conditions)
    _parse_structure_conditions(normalized, lower, conditions)
    _parse_high_break_conditions(normalized, lower, conditions, warnings)

    market_scope_override = markets or _expand_default_scope(default_market_scope)
    summary_parts = [", ".join(market_scope_override)] if markets else []
    summary_parts.extend(condition.label for condition in conditions)
    normalized_prompt = " / ".join(summary_parts) if summary_parts else normalized

    if not conditions and not markets:
        warnings.append("로컬 규칙 해석 결과가 제한적입니다.")

    return ParsedFilter(
        original_prompt=normalized,
        normalized_prompt=normalized_prompt,
        markets=markets,
        conditions=conditions,
        warnings=warnings,
        resolution_source="rule",
    )


def _parse_moving_average_conditions(text: str, lower: str, conditions: list[FilterCondition]) -> None:
    for window in (5, 20, 60, 120):
        if f"{window}일선 위" in text or f"price > ma{window}" in lower or f"ma{window} above" in lower:
            conditions.append(FilterCondition("price_vs_ma", ">", window, f"종가 > MA{window}"))
        if f"{window}일선 아래" in text or f"price < ma{window}" in lower or f"ma{window} below" in lower:
            conditions.append(FilterCondition("price_vs_ma", "<", window, f"종가 < MA{window}"))


def _parse_rsi_conditions(text: str, lower: str, conditions: list[FilterCondition]) -> None:
    rsi_match = re.search(r"rsi(?:14)?\s*(>=|<=|>|<|=)?\s*([0-9]+(?:\.[0-9]+)?)", lower)
    if rsi_match:
        operator = rsi_match.group(1) or ">="
        value = float(rsi_match.group(2))
        conditions.append(FilterCondition("RSI14", operator, value, f"RSI14 {operator} {value:g}"))
        return

    for keyword, operator in [("이상", ">="), ("이하", "<=")]:
        if "rsi" in lower and keyword in text:
            number_match = re.search(r"rsi(?:14)?\s*([0-9]+(?:\.[0-9]+)?)", lower)
            if number_match:
                value = float(number_match.group(1))
                conditions.append(FilterCondition("RSI14", operator, value, f"RSI14 {operator} {value:g}"))


def _parse_volume_conditions(text: str, lower: str, conditions: list[FilterCondition]) -> None:
    if "거래량 급증" in text or "volume surge" in lower:
        conditions.append(FilterCondition("VolumeRatio", ">=", 1.5, "거래량 비율 >= 1.5"))

    volume_ratio_match = re.search(
        r"거래량(?:이|은|는)?(?:\s*20일\s*평균\s*대비)?\s*([0-9]+(?:\.[0-9]+)?)배\s*이상",
        text,
    )
    if volume_ratio_match:
        value = float(volume_ratio_match.group(1))
        conditions.append(FilterCondition("VolumeRatio", ">=", value, f"거래량 비율 >= {value:g}"))


def _parse_fundamental_conditions(text: str, lower: str, conditions: list[FilterCondition]) -> None:
    field_patterns = {
        "PER": r"per\s*(>=|<=|>|<|=)?\s*([0-9]+(?:\.[0-9]+)?)",
        "PBR": r"pbr\s*(>=|<=|>|<|=)?\s*([0-9]+(?:\.[0-9]+)?)",
        "EPS": r"eps\s*(>=|<=|>|<|=)?\s*([0-9]+(?:\.[0-9]+)?)",
        "BPS": r"bps\s*(>=|<=|>|<|=)?\s*([0-9]+(?:\.[0-9]+)?)",
    }
    for field, pattern in field_patterns.items():
        match = re.search(pattern, lower)
        if match:
            operator = match.group(1) or "<="
            value = float(match.group(2))
            label = f"{field} {operator} {value:g}"
            conditions.append(FilterCondition(field, operator, value, label))

    korean_patterns = {
        "PER": r"per\s*([0-9]+(?:\.[0-9]+)?)\s*(이상|이하)",
        "PBR": r"pbr\s*([0-9]+(?:\.[0-9]+)?)\s*(이상|이하)",
        "EPS": r"eps\s*([0-9]+(?:\.[0-9]+)?)\s*(이상|이하)",
        "BPS": r"bps\s*([0-9]+(?:\.[0-9]+)?)\s*(이상|이하)",
    }
    for field, pattern in korean_patterns.items():
        match = re.search(pattern, lower)
        if match:
            value = float(match.group(1))
            operator = ">=" if match.group(2) == "이상" else "<="
            conditions.append(FilterCondition(field, operator, value, f"{field} {operator} {value:g}"))

    dividend_match = re.search(r"(?:배당수익률|div(?:idend)? yield)\s*(>=|<=|>|<|=)?\s*([0-9]+(?:\.[0-9]+)?)", lower)
    if dividend_match:
        operator = dividend_match.group(1) or ">="
        value = float(dividend_match.group(2))
        conditions.append(FilterCondition("DividendYield", operator, value, f"배당수익률 {operator} {value:g}"))
    else:
        dividend_korean_match = re.search(r"(?:배당수익률)\s*([0-9]+(?:\.[0-9]+)?)\s*(이상|이하)", text)
        if dividend_korean_match:
            value = float(dividend_korean_match.group(1))
            operator = ">=" if dividend_korean_match.group(2) == "이상" else "<="
            conditions.append(FilterCondition("DividendYield", operator, value, f"배당수익률 {operator} {value:g}"))


def _parse_return_conditions(
    text: str,
    lower: str,
    conditions: list[FilterCondition],
    warnings: list[str],
) -> None:
    return_match = re.search(r"([0-9]+)일\s*수익률\s*(>=|<=|>|<)?\s*([0-9]+(?:\.[0-9]+)?)", text)
    if not return_match:
        return

    window = int(return_match.group(1))
    operator = return_match.group(2) or ">="
    value = float(return_match.group(3))
    if window not in SUPPORTED_RETURN_WINDOWS:
        warnings.append(f"현재는 {sorted(SUPPORTED_RETURN_WINDOWS)}일 수익률만 직접 계산합니다.")
        return
    conditions.append(FilterCondition(f"Return{window}D", operator, value, f"{window}일 수익률 {operator} {value:g}%"))


def _parse_macd_conditions(text: str, lower: str, conditions: list[FilterCondition]) -> None:
    lowered_text = text.lower()
    if "macd 골든" in lowered_text or "macd golden" in lower:
        conditions.append(FilterCondition("MACD_CROSS", "==", "golden", "MACD 골든크로스"))
    if "macd 데드" in lowered_text or "macd dead" in lower:
        conditions.append(FilterCondition("MACD_CROSS", "==", "dead", "MACD 데드크로스"))
    if "macd가 시그널 위" in text or "macd > signal" in lower or "macd가 signal 위" in lower:
        conditions.append(FilterCondition("MACD_REL", ">", "signal", "MACD > Signal"))
    if "macd가 시그널 아래" in text or "macd < signal" in lower or "macd가 signal 아래" in lower:
        conditions.append(FilterCondition("MACD_REL", "<", "signal", "MACD < Signal"))


def _parse_structure_conditions(text: str, lower: str, conditions: list[FilterCondition]) -> None:
    if "정배열" in text or "bullish alignment" in lower:
        conditions.append(FilterCondition("MA_ALIGNMENT", "==", "bullish_5_20_60", "정배열(MA5 > MA20 > MA60)"))
    if "역배열" in text or "bearish alignment" in lower:
        conditions.append(FilterCondition("MA_ALIGNMENT", "==", "bearish_5_20_60", "역배열(MA5 < MA20 < MA60)"))


def _parse_high_break_conditions(
    text: str,
    lower: str,
    conditions: list[FilterCondition],
    warnings: list[str],
) -> None:
    high_match = re.search(r"([0-9]+)일\s*신고가", text)
    if high_match:
        window = int(high_match.group(1))
        if window not in SUPPORTED_HIGH_WINDOWS:
            warnings.append(f"현재는 {sorted(SUPPORTED_HIGH_WINDOWS)}일 신고가 조건만 직접 계산합니다.")
            return
        conditions.append(FilterCondition("NEW_HIGH", "==", window, f"{window}일 신고가"))
        return

    if "신고가" in text or "new high" in lower:
        conditions.append(FilterCondition("NEW_HIGH", "==", 60, "60일 신고가"))


def _extract_markets(lower_prompt: str) -> list[str]:
    matched: list[str] = []
    for market_id, aliases in MARKET_ALIASES.items():
        if any(alias in lower_prompt for alias in aliases):
            if market_id == "KRX_ALL":
                matched.extend(["KOSPI", "KOSDAQ"])
            elif market_id == "ALL":
                matched.extend(["KOSPI", "KOSDAQ", "TSE"])
            else:
                matched.append(market_id)
    return list(dict.fromkeys(matched))


def _expand_default_scope(default_market_scope: str) -> list[str]:
    if default_market_scope == "KRX_ALL":
        return ["KOSPI", "KOSDAQ"]
    if default_market_scope == "ALL":
        return ["KOSPI", "KOSDAQ", "TSE"]
    return [default_market_scope]


def looks_like_structured_query(prompt: str) -> bool:
    lower = prompt.lower()
    structured_tokens = [" and ", " or ", "rsi", "ma20", "ma60", "volume_ratio", "return20d", "market =="]
    return any(token in lower for token in structured_tokens)
