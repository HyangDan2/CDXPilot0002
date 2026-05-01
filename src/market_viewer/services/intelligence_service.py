from __future__ import annotations

import pandas as pd

from market_viewer.data.fundamental_service import FundamentalService, safe_metric_text
from market_viewer.models import FundamentalSnapshot, ReportRow, StockReference


def build_report_rows(
    stock: StockReference | None,
    price_frame: pd.DataFrame | None,
    snapshot: FundamentalSnapshot | None,
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
                ReportRow("가격/기술", "종가", safe_metric_text(latest.get("Close"), 0)),
                ReportRow("가격/기술", "거래량", safe_metric_text(latest.get("Volume"), 0)),
                ReportRow("가격/기술", "MA20", safe_metric_text(latest.get("MA20"))),
                ReportRow("가격/기술", "MA60", safe_metric_text(latest.get("MA60"))),
                ReportRow("가격/기술", "RSI14", safe_metric_text(latest.get("RSI14"))),
                ReportRow("가격/기술", "MACD", safe_metric_text(latest.get("MACD"))),
                ReportRow("가격/기술", "거래량비율", safe_metric_text(latest.get("VolumeRatio"))),
                ReportRow("가격/기술", "20일수익률", safe_metric_text(latest.get("Return20D")) + "%"),
            ]
        )
    if snapshot is not None:
        valuation_pairs = [
            ("PER", "PER"),
            ("PBR", "PBR"),
            ("EPS", "EPS"),
            ("BPS", "BPS"),
            ("배당수익률", "DividendYield"),
            ("DPS", "DPS"),
        ]
        for label, key in valuation_pairs:
            value = snapshot.values.get(key)
            note = snapshot.as_of_date if snapshot.as_of_date else ""
            rows.append(ReportRow("밸류에이션", label, safe_metric_text(value), note))
        for note in snapshot.notes:
            rows.append(ReportRow("밸류에이션", "비고", "-", note))
    return rows
