from __future__ import annotations

from datetime import datetime, timedelta
import math

import pandas as pd

from market_viewer.models import FundamentalSnapshot, StockReference


class FundamentalService:
    def __init__(self) -> None:
        self._snapshot_cache: dict[tuple[str, str], FundamentalSnapshot] = {}

    def load_snapshot(self, stock: StockReference) -> FundamentalSnapshot:
        cache_key = (stock.market, stock.code)
        if cache_key in self._snapshot_cache:
            return self._snapshot_cache[cache_key]

        snapshot = self._load_market_snapshot(stock)
        self._snapshot_cache[cache_key] = snapshot
        return snapshot

    def enrich_listing(self, listing: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
        frame = listing.copy()
        warnings: list[str] = []
        if frame.empty:
            return frame, warnings

        krx_markets = [market for market in ("KOSPI", "KOSDAQ") if market in set(frame["Market"].astype(str))]
        for market in krx_markets:
            try:
                market_frame = self._load_market_snapshot_frame(market)
            except Exception as exc:
                warnings.append(f"{market} 재무지표 로드 실패: {exc}")
                continue
            if market_frame.empty:
                continue
            market_mask = frame["Market"].astype(str) == market
            merged = frame.loc[market_mask].merge(market_frame, on="Code", how="left")
            for column in market_frame.columns:
                if column == "Code":
                    continue
                frame.loc[market_mask, column] = merged[column].values
        return frame, warnings

    def _load_market_snapshot(self, stock: StockReference) -> FundamentalSnapshot:
        if stock.market not in {"KOSPI", "KOSDAQ"}:
            return FundamentalSnapshot(notes=[f"{stock.market} 시장 재무지표는 현재 1차 지원 범위 밖입니다."])

        frame = self._load_market_snapshot_frame(stock.market)
        if frame.empty:
            return FundamentalSnapshot(notes=["재무지표 데이터가 비어 있습니다."])
        row_match = frame.loc[frame["Code"].astype(str) == str(stock.code)]
        if row_match.empty:
            return FundamentalSnapshot(notes=["선택 종목의 재무지표를 찾지 못했습니다."])

        row = row_match.iloc[0]
        values = {column: row.get(column) for column in row.index if column not in {"Code", "AsOfDate"}}
        return FundamentalSnapshot(as_of_date=str(row.get("AsOfDate", "")), values=values)

    def _load_market_snapshot_frame(self, market: str) -> pd.DataFrame:
        try:
            from pykrx import stock as pykrx_stock
        except Exception as exc:
            raise ValueError("pykrx가 설치되어 있지 않습니다. requirements 설치 후 다시 시도하세요.") from exc

        date_candidates = self._date_candidates()
        frame: pd.DataFrame | None = None
        last_error: Exception | None = None
        for date_str in date_candidates:
            try:
                candidate = self._fetch_market_fundamental_frame(pykrx_stock, date_str, market)
            except Exception as exc:
                last_error = exc
                continue
            if isinstance(candidate, pd.DataFrame) and not candidate.empty:
                frame = candidate.copy()
                frame["AsOfDate"] = date_str
                break
            if frame is not None:
                break
        if frame is None:
            raise ValueError(str(last_error or "KRX 재무지표를 조회하지 못했습니다."))

        normalized = frame.reset_index().rename(columns={"티커": "Code", "종목코드": "Code"})
        if "Code" not in normalized.columns:
            normalized = normalized.rename(columns={normalized.columns[0]: "Code"})

        normalized["Code"] = normalized["Code"].astype(str).str.zfill(6)
        normalized = self._normalize_fundamental_columns(normalized)
        desired_columns = ["Code", "AsOfDate", "PER", "PBR", "EPS", "BPS", "DividendYield", "DPS"]
        for column in desired_columns:
            if column not in normalized.columns:
                normalized[column] = pd.NA
        for column in desired_columns[2:]:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        return normalized[desired_columns]

    @staticmethod
    def _fetch_market_fundamental_frame(pykrx_stock, date_str: str, market: str) -> pd.DataFrame:
        # Prefer the market-wide endpoint. It is the documented API for
        # KOSPI/KOSDAQ fundamentals and avoids the more brittle by-ticker path.
        try:
            candidate = pykrx_stock.get_market_fundamental(date_str, market=market)
        except TypeError:
            candidate = pykrx_stock.get_market_fundamental(date_str)
        except Exception as exc:
            raise ValueError(f"{market} {date_str} 재무지표 조회 실패: {exc}") from exc

        if not isinstance(candidate, pd.DataFrame) or candidate.empty:
            raise ValueError(f"{market} {date_str} 재무지표가 비어 있습니다.")
        return candidate

    @staticmethod
    def _normalize_fundamental_columns(frame: pd.DataFrame) -> pd.DataFrame:
        normalized = frame.copy()
        rename_candidates = {
            "DIV": "DividendYield",
            "배당수익률": "DividendYield",
            "BPS(원)": "BPS",
            "EPS(원)": "EPS",
            "PER(배)": "PER",
            "PBR(배)": "PBR",
            "DPS(원)": "DPS",
        }
        for source, target in rename_candidates.items():
            if source in normalized.columns and target not in normalized.columns:
                normalized = normalized.rename(columns={source: target})
        return normalized

    @staticmethod
    def _date_candidates() -> list[str]:
        base = datetime.now()
        candidates: list[str] = []
        for days_back in range(0, 10):
            candidate = (base - timedelta(days=days_back)).strftime("%Y%m%d")
            if candidate not in candidates:
                candidates.append(candidate)
        return candidates


def safe_metric_text(value: object, digits: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and math.isnan(value):
        return "-"
    try:
        numeric = float(value)
    except Exception:
        text = str(value).strip()
        return text or "-"
    return f"{numeric:,.{digits}f}"
