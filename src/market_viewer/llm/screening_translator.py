from __future__ import annotations

import json
import re

from market_viewer.analysis.filter_models import ParsedFilter
from market_viewer.llm.client import send_chat_completion
from market_viewer.llm.screening_schema import sanitize_conditions, sanitize_markets, unique_non_empty
from market_viewer.models import LLMConfig


def translate_screening_prompt(
    config: LLMConfig,
    prompt: str,
    default_market_scope: str,
    local_fallback: ParsedFilter | None = None,
) -> ParsedFilter:
    primary = _translate_once(
        config=config,
        prompt=prompt,
        default_market_scope=default_market_scope,
        local_fallback=local_fallback,
        repair_target=None,
    )
    candidate = primary

    if _needs_repair(candidate, local_fallback):
        repaired = _translate_once(
            config=config,
            prompt=prompt,
            default_market_scope=default_market_scope,
            local_fallback=local_fallback,
            repair_target=candidate,
        )
        candidate = _choose_better_result(candidate, repaired)

    final = _merge_with_local_fallback(candidate, local_fallback)
    if not final.conditions and not final.markets and prompt.strip():
        raise ValueError("LLM이 스크리닝 조건을 충분히 구조화하지 못했습니다.")
    return final


def _translate_once(
    *,
    config: LLMConfig,
    prompt: str,
    default_market_scope: str,
    local_fallback: ParsedFilter | None,
    repair_target: ParsedFilter | None,
) -> ParsedFilter:
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(
        prompt=prompt,
        default_market_scope=default_market_scope,
        local_fallback=local_fallback,
        repair_target=repair_target,
    )
    response = send_chat_completion(config, system_prompt, user_prompt)
    payload = _parse_json_object(response)
    return _parsed_filter_from_payload(
        payload=payload,
        prompt=prompt,
        default_market_scope=default_market_scope,
        resolution_source="llm",
    )


def _build_system_prompt() -> str:
    return """너는 주식 스크리닝 자연어를 구조화된 조건으로 번역하는 전용 엔진이다.

역할:
- 사용자의 완전 자연어 스크리닝 요청을 앱이 실행할 수 있는 JSON으로 변환
- 가능한 한 사용자의 의도를 유지하되, 실행 가능한 기술적 조건으로 근사
- 애매한 표현도 최대한 버리지 말고 확실한 부분부터 구조화
- 설명문, 마크다운, 코드펜스, 주석, reasoning 텍스트를 절대 출력하지 않음

허용 market 값:
- KOSPI
- KOSDAQ
- TSE

허용 field 값:
- price_vs_ma
- RSI14
- VolumeRatio
- PER
- PBR
- EPS
- BPS
- DividendYield
- Return5D
- Return20D
- Return60D
- Return120D
- MACD_CROSS
- MACD_REL
- MA_ALIGNMENT
- NEW_HIGH

허용 operator 값:
- >
- >=
- <
- <=
- ==

값 규칙:
- MACD_CROSS value 는 golden 또는 dead
- MACD_REL value 는 signal
- MA_ALIGNMENT value 는 bullish_5_20_60 또는 bearish_5_20_60
- NEW_HIGH value 는 20, 60, 120 중 하나
- price_vs_ma value 는 5, 20, 60, 120 중 하나
- Return* 와 RSI14, VolumeRatio 값은 숫자
- PER, PBR, EPS, BPS, DividendYield 값은 숫자

자연어 해석 규칙:
- 시장이 명시되지 않으면 markets 는 빈 배열로 두고 현재 기본 시장 범위를 그대로 따름
- 사용자가 완전 자연어로 적어도 의도에 가장 가까운 조건을 만든다
- '강한 종목', '흐름 좋은 종목', '밀집 뒤 돌파', '거래가 붙는 종목', '눌림 뒤 반등', '전고점 근처 재시도'
  같은 표현도 가능한 범위에서 허용 field 로 근사 변환한다
- 모든 뜻을 완벽히 수치화할 수 없더라도, 확실한 일부 조건은 반드시 conditions 로 뽑아낸다
- 근사 해석한 표현, 빠진 수치, 불확실한 부분은 warnings 로 짧고 명확하게 남긴다
- normalized_prompt 는 사람이 읽기 쉬운 한 줄 요약이다
- label 은 UI 에 바로 보여줄 수 있도록 한국어로 짧게 만든다
- conditions 가 하나도 없으면 빈 배열을 유지하되, warnings 에 이유를 남긴다

근사 해석 예시:
- '추세가 좋다' -> price_vs_ma > 20 또는 MA_ALIGNMENT == bullish_5_20_60
- '최근 강하다' -> Return20D >= 5
- '거래가 붙는다' -> VolumeRatio >= 1.2
- '전고점 근처' -> NEW_HIGH == 60
- '눌림 뒤 반등' -> price_vs_ma > 20 와 Return5D >= 0 조합으로 일부 근사 가능

반드시 아래 JSON 스키마 하나만 반환하라:
{
  "markets": ["KOSDAQ"],
  "normalized_prompt": "KOSDAQ / 종가 > MA20 / RSI14 >= 60",
  "conditions": [
    {"field": "price_vs_ma", "operator": ">", "value": 20, "label": "종가 > MA20"},
    {"field": "RSI14", "operator": ">=", "value": 60, "label": "RSI14 >= 60"}
  ],
  "warnings": []
}
"""


def _build_user_prompt(
    *,
    prompt: str,
    default_market_scope: str,
    local_fallback: ParsedFilter | None,
    repair_target: ParsedFilter | None,
) -> str:
    local_hint = ""
    if local_fallback is not None:
        local_conditions = ", ".join(condition.label for condition in local_fallback.conditions) or "없음"
        local_warnings = ", ".join(local_fallback.warnings) or "없음"
        local_hint = f"""

로컬 보조 해석:
- 감지된 조건: {local_conditions}
- 경고: {local_warnings}
- 이 정보는 참고용이다. 더 자연스럽고 타당한 구조화가 가능하면 네가 보정해도 된다.
"""

    repair_hint = ""
    if repair_target is not None:
        repair_conditions = ", ".join(condition.label for condition in repair_target.conditions) or "없음"
        repair_warnings = ", ".join(repair_target.warnings) or "없음"
        repair_hint = f"""

이전 시도 보정:
- 이전 해석 조건: {repair_conditions}
- 이전 경고: {repair_warnings}
- 이전 결과가 비어 있거나 부족했다. 이번에는 확실한 일부 조건이라도 더 적극적으로 추출해라.
- 단, 허용된 market / field / operator / value 규칙은 반드시 지켜라.
"""

    return f"""기본 시장 범위: {default_market_scope}

사용자 스크리닝 프롬프트:
{prompt}
{local_hint}
{repair_hint}

작업:
1. 사용자의 완전 자연어 의도를 최대한 보존해 구조화
2. 확실한 내용은 conditions 로, 애매한 내용은 warnings 로 분리
3. JSON 하나만 반환
4. 아무 설명도 덧붙이지 말 것
"""


def _parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("LLM 스크리닝 응답이 비어 있습니다.")
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"LLM 스크리닝 응답을 JSON으로 해석하지 못했습니다: {cleaned[:300]}")


def _parsed_filter_from_payload(
    *,
    payload: dict,
    prompt: str,
    default_market_scope: str,
    resolution_source: str,
) -> ParsedFilter:
    markets, market_warnings = sanitize_markets(payload.get("markets", []))
    conditions, condition_warnings = sanitize_conditions(payload.get("conditions", []))
    warnings = [str(warning).strip() for warning in payload.get("warnings", []) if str(warning).strip()]
    warnings.extend(market_warnings)
    warnings.extend(condition_warnings)
    normalized_prompt = str(payload.get("normalized_prompt", "")).strip() or prompt.strip() or default_market_scope

    return ParsedFilter(
        original_prompt=prompt.strip(),
        normalized_prompt=normalized_prompt,
        markets=markets,
        conditions=conditions,
        warnings=unique_non_empty(warnings),
        resolution_source=resolution_source,
    )


def _needs_repair(parsed: ParsedFilter, local_fallback: ParsedFilter | None) -> bool:
    if parsed.conditions:
        return False
    if local_fallback is not None and local_fallback.conditions:
        return True
    return len(parsed.warnings) <= 1


def _choose_better_result(primary: ParsedFilter, repaired: ParsedFilter) -> ParsedFilter:
    primary_score = _score_result(primary)
    repaired_score = _score_result(repaired)
    return repaired if repaired_score >= primary_score else primary


def _score_result(parsed: ParsedFilter) -> int:
    return (len(parsed.conditions) * 10) + (len(parsed.markets) * 3) - len(parsed.warnings)


def _merge_with_local_fallback(parsed: ParsedFilter, local_fallback: ParsedFilter | None) -> ParsedFilter:
    if local_fallback is None:
        return parsed

    merged_markets = parsed.markets or local_fallback.markets
    merged_conditions = list(parsed.conditions)
    merged_warnings = list(parsed.warnings)

    if not parsed.conditions and local_fallback.conditions:
        merged_conditions = list(local_fallback.conditions)
        merged_warnings.append("LLM이 조건을 충분히 구조화하지 못해 로컬 규칙 조건을 함께 반영했습니다.")
    else:
        seen = {(condition.field, condition.operator, str(condition.value)) for condition in merged_conditions}
        for condition in local_fallback.conditions:
            key = (condition.field, condition.operator, str(condition.value))
            if key not in seen:
                merged_conditions.append(condition)
                seen.add(key)

    return ParsedFilter(
        original_prompt=parsed.original_prompt,
        normalized_prompt=parsed.normalized_prompt,
        markets=merged_markets,
        conditions=merged_conditions,
        warnings=unique_non_empty(merged_warnings),
        resolution_source=parsed.resolution_source,
    )
