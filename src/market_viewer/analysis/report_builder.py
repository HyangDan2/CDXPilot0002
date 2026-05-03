from __future__ import annotations

import pandas as pd

from market_viewer.models import FundamentalSnapshot, LLMConfig, StockReference


def _safe_value(value: object, digits: int = 2) -> str:
    if value is None:
        return "-"
    if pd.isna(value):
        return "-"
    return f"{float(value):,.{digits}f}"


def build_stock_report(
    stock: StockReference,
    frame: pd.DataFrame,
    snapshot: FundamentalSnapshot | None = None,
) -> str:
    latest = frame.iloc[-1]
    previous = frame.iloc[-2] if len(frame) > 1 else latest

    close = float(latest["Close"])
    previous_close = float(previous["Close"])
    change_pct = ((close / previous_close) - 1) * 100 if previous_close else 0.0
    ma20 = latest.get("MA20")
    ma60 = latest.get("MA60")
    rsi14 = latest.get("RSI14")
    macd = latest.get("MACD")
    macd_signal = latest.get("MACDSignal")
    volume_ratio = latest.get("VolumeRatio")
    return_20d = latest.get("Return20D")

    trend = "중립"
    if pd.notna(ma20) and close > ma20:
        trend = "단기 상승 우위"
    if pd.notna(ma60) and close < ma60:
        trend = "중기 약세 경계"

    fundamental_lines = ""
    if snapshot is not None:
        values = snapshot.values
        fundamental_lines = f"""

## 키움 기본정보 / 재무 스냅샷
- 기준일: {snapshot.as_of_date or "-"}
- PER / PBR / ROE: {_safe_value(values.get("PER"))} / {_safe_value(values.get("PBR"))} / {_safe_value(values.get("ROE"))}
- EPS / BPS: {_safe_value(values.get("EPS"))} / {_safe_value(values.get("BPS"))}
- 매출액 / 영업이익 / 순이익: {_safe_value(values.get("Revenue"), 0)} / {_safe_value(values.get("OperatingProfit"), 0)} / {_safe_value(values.get("NetIncome"), 0)}
- 시가총액 / 외인소진률: {_safe_value(values.get("MarketCap"), 0)} / {_safe_value(values.get("ForeignOwnershipRatio"))}
"""
        if snapshot.notes:
            fundamental_lines += "\n" + "\n".join(f"- 비고: {note}" for note in snapshot.notes)

    return f"""# {stock.name} ({stock.code})

## 종목 정보
- 시장: {stock.market}
- 국가/통화: {stock.country} / {stock.currency}
- 종가: {_safe_value(close)} {stock.currency}
- 전일 대비: {_safe_value(change_pct)}%
- 거래량: {_safe_value(latest.get("Volume"), 0)}

## 기술 요약
- 현재 해석: {trend}
- MA20: {_safe_value(ma20)} / MA60: {_safe_value(ma60)}
- RSI14: {_safe_value(rsi14)}
- MACD / Signal: {_safe_value(macd)} / {_safe_value(macd_signal)}
- 거래량 비율: {_safe_value(volume_ratio)}
- 20일 수익률: {_safe_value(return_20d)}%
{fundamental_lines}

## 체크포인트
- 차트는 드래그로 좌우 기간 이동, 휠로 확대/축소할 수 있습니다.
- 스크리너 조건은 메뉴바에서 관리하고, 분석 요청은 우측 입력창에서 관리합니다.
- 프롬프트 레이어는 메뉴바에서 토글해 LLM 분석 톤과 관점을 조절합니다.
"""


def build_workspace_summary(
    market_scope: str,
    stock: StockReference | None,
    filter_prompt: str,
    active_layer_names: list[str],
    llm_config: LLMConfig,
    chart_range_text: str,
) -> str:
    stock_text = stock.display_name if stock else "선택된 종목 없음"
    filter_text = filter_prompt.strip() or "없음"
    layers_text = ", ".join(active_layer_names) if active_layer_names else "없음"
    llm_text = f"{llm_config.model} @ {llm_config.base_url}" if llm_config.model else "미설정"
    return f"""## 현재 세션

- 시장 범위: {market_scope}
- 선택 종목: {stock_text}
- 스크리너 조건: {filter_text}
- 활성 프롬프트 레이어: {layers_text}
- 차트 기간: {chart_range_text}
- LLM 연결: {llm_text}
"""
