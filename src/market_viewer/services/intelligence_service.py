from __future__ import annotations

import pandas as pd

from market_viewer.models import FundamentalSnapshot, ReportRow, StockReference


def _safe_metric_text(value: object, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.{digits}f}"


def build_report_rows(
    stock: StockReference | None,
    price_frame: pd.DataFrame | None,
    snapshot: FundamentalSnapshot | None = None,
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
    if snapshot is not None:
        metric_pairs = [
            ("PER", "PER"),
            ("PBR", "PBR"),
            ("ROE", "ROE"),
            ("EPS", "EPS"),
            ("BPS", "BPS"),
            ("매출액", "Revenue"),
            ("영업이익", "OperatingProfit"),
            ("순이익", "NetIncome"),
            ("시가총액", "MarketCap"),
            ("외인소진률", "ForeignOwnershipRatio"),
        ]
        for label, key in metric_pairs:
            value = snapshot.values.get(key)
            rows.append(ReportRow("키움 기본정보", label, _safe_metric_text(value), snapshot.as_of_date))
        for note in snapshot.notes:
            rows.append(ReportRow("키움 기본정보", "비고", "-", note))
    return rows
