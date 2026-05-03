from __future__ import annotations

import pandas as pd

from market_viewer.models import ReportRow, StockReference


def _safe_metric_text(value: object, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.{digits}f}"


def build_report_rows(
    stock: StockReference | None,
    price_frame: pd.DataFrame | None,
) -> list[ReportRow]:
    rows: list[ReportRow] = []
    if stock is not None:
        rows.extend(
            [
                ReportRow("기본정보", "시장", stock.market),
                ReportRow("기본정보", "코드", stock.code),
                ReportRow("기본정보", "통화", stock.currency),
            ]
        )
    if price_frame is not None and not price_frame.empty:
        latest = price_frame.iloc[-1]
        rows.extend(
            [
                ReportRow("가격/기술", "종가", _safe_metric_text(latest.get("Close"), 0)),
                ReportRow("가격/기술", "거래량", _safe_metric_text(latest.get("Volume"), 0)),
                ReportRow("가격/기술", "MA20", _safe_metric_text(latest.get("MA20"))),
                ReportRow("가격/기술", "MA60", _safe_metric_text(latest.get("MA60"))),
                ReportRow("가격/기술", "RSI14", _safe_metric_text(latest.get("RSI14"))),
                ReportRow("가격/기술", "MACD", _safe_metric_text(latest.get("MACD"))),
                ReportRow("가격/기술", "거래량비율", _safe_metric_text(latest.get("VolumeRatio"))),
                ReportRow("가격/기술", "20일수익률", _safe_metric_text(latest.get("Return20D")) + "%"),
            ]
        )
    return rows
