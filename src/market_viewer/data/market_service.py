from __future__ import annotations

from dataclasses import dataclass
import time

import pandas as pd

from market_viewer.data.kiwoom.provider import KiwoomMarketDataProvider
from market_viewer.data.market_registry import get_listing_sources
from market_viewer.models import FundamentalSnapshot, KiwoomConfig, StockReference


@dataclass(slots=True)
class PriceErrorEntry:
    message: str
    created_at: float
    retryable: bool


class MarketService:
    RETRYABLE_ERROR_TTL_SECONDS = 120.0

    def __init__(self, kiwoom_config: KiwoomConfig) -> None:
        self._provider = KiwoomMarketDataProvider(kiwoom_config)
        self._listing_cache: dict[str, pd.DataFrame] = {}
        self._price_cache: dict[tuple[str, str, int], pd.DataFrame] = {}
        self._fundamental_cache: dict[tuple[str, str], FundamentalSnapshot] = {}
        self._price_error_cache: dict[tuple[str, str, int], PriceErrorEntry] = {}

    def test_connection(self) -> str:
        return self._provider.test_connection()

    def load_listing(self, market_scope: str) -> pd.DataFrame:
        frames = [self._load_source_listing(source) for source in get_listing_sources(market_scope)]
        if not frames:
            return pd.DataFrame(columns=["Code", "Name", "Market", "Country", "Currency", "Close", "ChangePct", "Volume"])
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

        try:
            frame = self._provider.load_price_history(stock, months=months)
        except Exception as exc:
            message = f"{stock.display_name} 가격 데이터를 가져오지 못했습니다. {exc}"
            self._remember_price_error(cache_key, message, retryable=True)
            raise ValueError(message) from exc

        required_columns = {"Date", "Open", "High", "Low", "Close", "Volume"}
        missing_columns = [column for column in required_columns if column not in frame.columns]
        if missing_columns:
            message = f"가격 데이터 필수 컬럼이 없습니다: {', '.join(sorted(missing_columns))}"
            self._remember_price_error(cache_key, message, retryable=False)
            raise ValueError(message)
        frame = frame.dropna(subset=["Date", "Open", "High", "Low", "Close", "Volume"]).reset_index(drop=True)
        if frame.empty:
            message = "가격 데이터에 유효한 OHLCV 행이 없습니다."
            self._remember_price_error(cache_key, message, retryable=False)
            raise ValueError(message)
        self._price_cache[cache_key] = frame
        return frame.copy()

    def load_fundamental_snapshot(self, stock: StockReference) -> FundamentalSnapshot:
        cache_key = (stock.market, stock.code)
        if cache_key not in self._fundamental_cache:
            self._fundamental_cache[cache_key] = self._provider.load_fundamental_snapshot(stock)
        return self._fundamental_cache[cache_key]

    def _remember_price_error(self, cache_key: tuple[str, str, int], message: str, retryable: bool) -> None:
        self._price_error_cache[cache_key] = PriceErrorEntry(
            message=message,
            created_at=time.monotonic(),
            retryable=retryable,
        )

    def _load_source_listing(self, source_market: str) -> pd.DataFrame:
        if source_market in self._listing_cache:
            return self._listing_cache[source_market].copy()
        listing = self._provider.load_listing(source_market)
        self._listing_cache[source_market] = listing
        return listing.copy()
