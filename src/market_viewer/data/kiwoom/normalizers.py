from __future__ import annotations

from datetime import datetime

import pandas as pd


def clean_code(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith("A") and len(text) >= 7:
        text = text[1:]
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6) if text.isdigit() else text


def parse_number(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    prefix = ""
    while text.startswith(("+", "-")):
        prefix += text[0]
        text = text[1:]
    sign = -1 if "-" in prefix else 1
    if not text:
        return None
    try:
        return sign * float(text)
    except ValueError:
        return None


def parse_int(value: object) -> int | None:
    number = parse_number(value)
    if number is None:
        return None
    return int(number)


def parse_absolute_number(value: object) -> float | None:
    number = parse_number(value)
    if number is None:
        return None
    return abs(number)


def normalize_listing_rows(rows: list[dict], market_id: str) -> pd.DataFrame:
    normalized: list[dict] = []
    for row in rows:
        code = clean_code(row.get("code"))
        name = str(row.get("name") or "").strip()
        if not code or not name:
            continue
        normalized.append(
            {
                "Code": code,
                "Name": name,
                "Market": market_id,
                "Country": "KR",
                "Currency": "KRW",
                "Close": parse_absolute_number(row.get("lastPrice")),
                "ChangePct": pd.NA,
                "Volume": pd.NA,
                "State": str(row.get("state") or "").strip(),
                "Sector": str(row.get("upName") or "").strip(),
                "MarketCode": str(row.get("marketCode") or "").strip(),
                "NxtEnable": str(row.get("nxtEnable") or "").strip(),
            }
        )
    return pd.DataFrame(normalized)


def normalize_daily_chart_rows(rows: list[dict]) -> pd.DataFrame:
    normalized: list[dict] = []
    for row in rows:
        date_text = str(row.get("dt") or "").strip()
        if not date_text:
            continue
        normalized.append(
            {
                "Date": datetime.strptime(date_text, "%Y%m%d"),
                "Open": parse_absolute_number(row.get("open_pric")),
                "High": parse_absolute_number(row.get("high_pric")),
                "Low": parse_absolute_number(row.get("low_pric")),
                "Close": parse_absolute_number(row.get("cur_prc")),
                "Volume": parse_absolute_number(row.get("trde_qty")),
            }
        )
    frame = pd.DataFrame(normalized)
    if frame.empty:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    frame = frame.dropna(subset=["Date", "Open", "High", "Low", "Close", "Volume"])
    return frame.sort_values("Date").reset_index(drop=True)


def normalize_basic_info(payload: dict) -> dict[str, float | int | str | None]:
    return {
        "PER": parse_number(payload.get("per")),
        "PBR": parse_number(payload.get("pbr")),
        "EPS": parse_number(payload.get("eps")),
        "BPS": parse_number(payload.get("bps")),
        "ROE": parse_number(payload.get("roe")),
        "Revenue": parse_number(payload.get("sale_amt")),
        "OperatingProfit": parse_number(payload.get("bus_pro")),
        "NetIncome": parse_number(payload.get("cup_nga")),
        "MarketCap": parse_number(payload.get("mac")),
        "SharesOutstanding": parse_int(payload.get("flo_stk")),
        "FloatShares": parse_int(payload.get("dstr_stk")),
        "ForeignOwnershipRatio": parse_number(payload.get("for_exh_rt")),
        "SettlementMonth": str(payload.get("setl_mm") or "").strip(),
    }
