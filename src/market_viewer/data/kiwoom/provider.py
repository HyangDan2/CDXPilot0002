from __future__ import annotations

from datetime import datetime

import pandas as pd

from market_viewer.data.kiwoom import endpoints
from market_viewer.data.kiwoom.client import KiwoomRestClient
from market_viewer.data.kiwoom.normalizers import normalize_basic_info, normalize_daily_chart_rows, normalize_listing_rows
from market_viewer.models import FundamentalSnapshot, KiwoomConfig, StockReference


MARKET_TO_KIWOOM = {
    "KOSPI": "0",
    "KOSDAQ": "10",
}


class KiwoomMarketDataProvider:
    def __init__(self, config: KiwoomConfig) -> None:
        self._client = KiwoomRestClient(config)

    def test_connection(self) -> str:
        return self._client.test_connection()

    def load_listing(self, market_id: str) -> pd.DataFrame:
        mrkt_tp = MARKET_TO_KIWOOM.get(market_id)
        if not mrkt_tp:
            raise ValueError(f"키움 REST backend가 지원하지 않는 시장입니다: {market_id}")
        response = self._client.post(endpoints.API_STOCK_LIST, endpoints.STOCK_INFO, {"mrkt_tp": mrkt_tp})
        rows = response.payload.get("list", [])
        if not isinstance(rows, list):
            raise ValueError("키움 종목정보 리스트 응답에서 list를 찾지 못했습니다.")
        return normalize_listing_rows([row for row in rows if isinstance(row, dict)], market_id)

    def load_price_history(self, stock: StockReference, months: int = 18) -> pd.DataFrame:
        body = {
            "stk_cd": stock.code,
            "base_dt": datetime.now().strftime("%Y%m%d"),
            "upd_stkpc_tp": "1",
        }
        rows = self._client.post_all_pages(
            endpoints.API_DAILY_CHART,
            endpoints.CHART,
            body,
            list_key="stk_dt_pole_chart_qry",
            max_pages=8,
        )
        frame = normalize_daily_chart_rows(rows)
        if frame.empty:
            raise ValueError(f"{stock.display_name} 일봉 데이터가 비어 있습니다.")
        cutoff = pd.Timestamp.now() - pd.DateOffset(months=months)
        return frame[frame["Date"] >= cutoff].reset_index(drop=True)

    def load_fundamental_snapshot(self, stock: StockReference) -> FundamentalSnapshot:
        response = self._client.post(endpoints.API_STOCK_BASIC, endpoints.STOCK_INFO, {"stk_cd": stock.code})
        values = normalize_basic_info(response.payload)
        notes = [
            "키움 기본정보 재무 필드는 외부 벤더 제공 스냅샷이며 실시간 재무제표가 아닙니다.",
        ]
        return FundamentalSnapshot(as_of_date=datetime.now().strftime("%Y-%m-%d"), values=values, notes=notes)
