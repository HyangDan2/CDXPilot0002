from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import time

import pandas as pd

from market_viewer.data.market_registry import get_listing_sources
from market_viewer.models import StockReference


@dataclass(slots=True)
class PriceErrorEntry:
    message: str
    created_at: float
    retryable: bool


class MarketService:
    RETRYABLE_ERROR_TTL_SECONDS = 120.0

    def __init__(self) -> None:
        self._listing_cache: dict[str, pd.DataFrame] = {}
        self._price_cache: dict[tuple[str, str, int], pd.DataFrame] = {}
        self._price_error_cache: dict[tuple[str, str, int], PriceErrorEntry] = {}

    def load_listing(self, market_scope: str) -> pd.DataFrame:
        frames = [self._load_source_listing(source) for source in get_listing_sources(market_scope)]
        listing = pd.concat(frames, ignore_index=True)
        listing = listing.sort_values(["Market", "Name"]).reset_index(drop=True)
        return listing

    def build_stock_reference(self, row: pd.Series) -> StockReference:
        return StockReference(
            code=str(row.get("Code", "")),
            name=str(row.get("Name", "")),
            market=str(row.get("Market", "")),
            country=str(row.get("Country", "")),
            currency=str(row.get("Currency", "")),
        )

    def load_price_history(self, stock: StockReference, months: int = 18) -> pd.DataFrame:
        cache_key = (stock.market, stock.code, months)
        if cache_key in self._price_cache:
            return self._price_cache[cache_key].copy()
        cached_error = self._price_error_cache.get(cache_key)
        if cached_error is not None:
            if cached_error.retryable and (time.monotonic() - cached_error.created_at) > self.RETRYABLE_ERROR_TTL_SECONDS:
                self._price_error_cache.pop(cache_key, None)
            else:
                raise ValueError(cached_error.message)

        start = (datetime.now() - timedelta(days=months * 31)).strftime("%Y-%m-%d")
        symbols = self._price_symbol_candidates(stock)
        frame = None
        errors: list[str] = []
        for symbol in symbols:
            try:
                import FinanceDataReader as fdr

                candidate = fdr.DataReader(symbol, start).reset_index()
                if not candidate.empty:
                    frame = candidate
                    break
            except Exception as exc:
                errors.append(f"{symbol}: {exc}")
                continue

        if frame is None or frame.empty:
            attempted = ", ".join(symbols[:4])
            detail = f" (시도: {attempted})" if attempted else ""
            message = f"{stock.display_name} 가격 데이터를 가져오지 못했습니다{detail}."
            self._remember_price_error(cache_key, message, retryable=True)
            raise ValueError(message)

        frame = self._normalize_price_columns(frame)
        required_columns = {"Date", "Open", "High", "Low", "Close", "Volume"}
        missing_columns = [column for column in required_columns if column not in frame.columns]
        if missing_columns:
            message = f"가격 데이터 필수 컬럼이 없습니다: {', '.join(sorted(missing_columns))}"
            self._remember_price_error(cache_key, message, retryable=False)
            raise ValueError(message)

        frame["Date"] = pd.to_datetime(frame["Date"])
        for column in ["Open", "High", "Low", "Close", "Volume"]:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.sort_values("Date").reset_index(drop=True)
        frame = frame.dropna(subset=["Date", "Open", "High", "Low", "Close", "Volume"]).reset_index(drop=True)
        if frame.empty:
            message = "가격 데이터에 유효한 OHLCV 행이 없습니다."
            self._remember_price_error(cache_key, message, retryable=False)
            raise ValueError(message)
        self._price_cache[cache_key] = frame
        return frame.copy()

    def _remember_price_error(self, cache_key: tuple[str, str, int], message: str, retryable: bool) -> None:
        self._price_error_cache[cache_key] = PriceErrorEntry(
            message=message,
            created_at=time.monotonic(),
            retryable=retryable,
        )

    def _load_source_listing(self, source_market: str) -> pd.DataFrame:
        if source_market in self._listing_cache:
            return self._listing_cache[source_market].copy()

        import FinanceDataReader as fdr

        listing = fdr.StockListing(source_market).copy()
        listing = self._normalize_listing(listing, source_market)
        self._listing_cache[source_market] = listing
        return listing.copy()

    @staticmethod
    def _normalize_price_columns(frame: pd.DataFrame) -> pd.DataFrame:
        aliases = {
            "Date": {"date", "data", "datetime", "time", "index"},
            "Open": {"open", "opening"},
            "High": {"high"},
            "Low": {"low"},
            "Close": {"close", "adj close", "adjclose", "closing"},
            "Volume": {"volume", "vol"},
        }
        renamed = frame.copy()
        lower_to_original = {str(column).strip().lower(): column for column in renamed.columns}
        rename_map: dict[object, str] = {}
        for canonical, candidates in aliases.items():
            if canonical in renamed.columns:
                continue
            for candidate in candidates:
                original = lower_to_original.get(candidate)
                if original is not None:
                    rename_map[original] = canonical
                    break
        if rename_map:
            renamed = renamed.rename(columns=rename_map)
        return renamed

    def _normalize_listing(self, listing: pd.DataFrame, market_id: str) -> pd.DataFrame:
        code_column = "Code" if "Code" in listing.columns else "Symbol"
        name_column = "Name" if "Name" in listing.columns else "Name"

        frame = pd.DataFrame()
        frame["Code"] = listing[code_column].map(lambda value: self._normalize_code(value, market_id))
        frame["Name"] = listing[name_column].astype(str).str.strip()
        frame["Market"] = market_id
        frame["Country"] = "JP" if market_id == "TSE" else "KR"
        frame["Currency"] = "JPY" if market_id == "TSE" else "KRW"

        close_column = "Close" if "Close" in listing.columns else None
        change_column = "ChagesRatio" if "ChagesRatio" in listing.columns else "ChangesRatio" if "ChangesRatio" in listing.columns else None
        volume_column = "Volume" if "Volume" in listing.columns else None

        frame["Close"] = pd.to_numeric(listing[close_column], errors="coerce") if close_column else pd.NA
        frame["ChangePct"] = (
            pd.to_numeric(listing[change_column], errors="coerce") if change_column else pd.NA
        )
        frame["Volume"] = pd.to_numeric(listing[volume_column], errors="coerce") if volume_column else pd.NA
        frame = frame.dropna(subset=["Code", "Name"]).reset_index(drop=True)
        frame = frame[frame["Code"].astype(str).str.strip() != ""].reset_index(drop=True)
        frame = frame[frame["Name"].astype(str).str.strip() != ""].reset_index(drop=True)
        return frame

    @staticmethod
    def _normalize_code(value: object, market_id: str) -> str:
        text = str(value).strip()
        if text.endswith(".0"):
            text = text[:-2]
        if market_id in {"KOSPI", "KOSDAQ"} and text.isdigit():
            return text.zfill(6)
        return text

    @staticmethod
    def _price_symbol_candidates(stock: StockReference) -> list[str]:
        candidates = [stock.code]
        if stock.market in {"KOSPI", "KOSDAQ"} and stock.code.isdigit():
            candidates.append(stock.code.zfill(6))
        if stock.market == "TSE" and stock.code.isdigit():
            code4 = stock.code.zfill(4)
            candidates = [
                f"TSE:{code4}",
                f"{code4}.T",
                f"YAHOO:{code4}.T",
            ]
        return list(dict.fromkeys(candidates))
