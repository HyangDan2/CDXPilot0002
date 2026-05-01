from __future__ import annotations

import math

import pandas as pd

from market_viewer.models import StockReference
from market_viewer.prompt_layers.layer_registry import get_prompt_layer


def build_system_prompt(active_layer_ids: list[str]) -> str:
    base_lines = [
        "당신은 데스크톱 주식 분석 도우미다.",
        "반드시 제공된 데이터만 사용하라. 외부 뉴스, 재무, 수급, 펀더멘털은 주어지지 않았으면 언급하지 마라.",
        "투자 자문으로 단정하지 말고 관측된 지표를 기반으로 설명하라.",
        "모르는 값은 추정하지 말고 데이터 부족이라고 짧게 명시하라.",
        "응답은 Markdown으로 구성하라.",
        "질문이 모호해도 가능한 범위에서 직접 답하고, 필요한 가정은 1줄로만 명시하라.",
        "항상 결론보다 근거를 먼저 제시하되, 장황한 배경설명은 생략하라.",
    ]
    for layer_id in active_layer_ids:
        layer = get_prompt_layer(layer_id)
        if layer:
            base_lines.append(layer.system_text)
    return "\n".join(base_lines)


def build_user_prompt(
    stock: StockReference,
    frame: pd.DataFrame,
    filter_prompt: str,
    user_request: str,
) -> str:
    snapshot = _latest_snapshot_markdown(stock, frame)
    latest_rows = _latest_rows_markdown(frame)
    filter_text = filter_prompt.strip() or "없음"
    user_text = user_request.strip() or "현재 종목의 핵심 포인트를 요약해줘."
    return f"""현재 선택된 종목 정보를 참고해 분석해줘.

## 필수 출력 형식
반드시 아래 4개 섹션만 사용해 답변하라.

## 한줄 요약
- 현재 상태를 1~2문장으로 요약

## 핵심 근거
- 3~6개 bullet
- 각 bullet에는 가능하면 숫자 또는 비교식 포함

## 리스크
- 2~4개 bullet
- 무효화 조건 또는 해석 한계 포함

## 체크포인트
- 다음에 확인할 조건 2~4개

## 응답 규칙
- 제공된 지표와 최근 캔들만 기준으로 설명
- 설명보다 판정과 근거를 우선
- 숫자 또는 비교식이 있으면 함께 제시
- 불확실하면 데이터 부족이라고 짧게 명시
- 사용자의 질문이 넓어도 반드시 위 형식으로 직접 답변
- 과도한 서론, 일반론, 투자 경고 반복은 금지

## 스크리너 조건
{filter_text}

## 종목 스냅샷
{snapshot}

## 최근 3개 캔들
{latest_rows}

## 사용자 요청
{user_text}
"""


def _latest_rows_markdown(frame: pd.DataFrame) -> str:
    columns = ["Date", "Open", "High", "Low", "Close", "Volume", "RSI14", "MACD"]
    tail = frame[columns].tail(3).copy()
    tail["Date"] = tail["Date"].dt.strftime("%Y-%m-%d")
    headers = list(tail.columns)
    markdown_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in tail.iterrows():
        values = [_format_cell(row[column]) for column in headers]
        markdown_lines.append("| " + " | ".join(values) + " |")
    return "\n".join(markdown_lines)


def _latest_snapshot_markdown(stock: StockReference, frame: pd.DataFrame) -> str:
    latest = frame.iloc[-1]
    previous = frame.iloc[-2] if len(frame) > 1 else latest
    close = float(latest["Close"])
    previous_close = float(previous["Close"])
    change_pct = ((close / previous_close) - 1.0) * 100 if previous_close else 0.0
    return "\n".join(
        [
            f"- 종목: {stock.display_name}",
            f"- 국가/통화: {stock.country} / {stock.currency}",
            f"- 종가: {_format_number(close)}",
            f"- 전일 대비: {_format_number(change_pct)}%",
            f"- MA20 / MA60: {_format_number(latest.get('MA20'))} / {_format_number(latest.get('MA60'))}",
            f"- RSI14: {_format_number(latest.get('RSI14'))}",
            f"- MACD / Signal: {_format_number(latest.get('MACD'))} / {_format_number(latest.get('MACDSignal'))}",
            f"- 거래량 / 비율: {_format_number(latest.get('Volume'), 0)} / {_format_number(latest.get('VolumeRatio'))}",
            f"- 20일 수익률: {_format_number(latest.get('Return20D'))}%",
        ]
    )


def _format_number(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    number = float(value)
    if math.isnan(number):
        return "-"
    return f"{number:,.{digits}f}"


def _format_cell(value) -> str:
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if value is None or pd.isna(value):
        return "-"
    if isinstance(value, (int, float)):
        digits = 0 if abs(float(value)) >= 1000 else 2
        return _format_number(value, digits)
    return str(value)
