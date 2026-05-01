from __future__ import annotations

from market_viewer.models import MarketDefinition


MARKET_REGISTRY: dict[str, MarketDefinition] = {
    "KOSPI": MarketDefinition(
        id="KOSPI",
        label="KOSPI",
        country="KR",
        currency="KRW",
        listing_sources=("KOSPI",),
    ),
    "KOSDAQ": MarketDefinition(
        id="KOSDAQ",
        label="KOSDAQ",
        country="KR",
        currency="KRW",
        listing_sources=("KOSDAQ",),
    ),
    "TSE": MarketDefinition(
        id="TSE",
        label="Tokyo Stock Exchange",
        country="JP",
        currency="JPY",
        listing_sources=("TSE",),
    ),
    "KRX_ALL": MarketDefinition(
        id="KRX_ALL",
        label="KRX ALL",
        country="KR",
        currency="KRW",
        listing_sources=("KOSPI", "KOSDAQ"),
    ),
    "ALL": MarketDefinition(
        id="ALL",
        label="KR + JP ALL",
        country="MULTI",
        currency="MULTI",
        listing_sources=("KOSPI", "KOSDAQ", "TSE"),
    ),
}


DEFAULT_MARKET_ORDER = ["KOSPI", "KOSDAQ", "KRX_ALL", "TSE", "ALL"]


def get_market_definition(market_id: str) -> MarketDefinition:
    return MARKET_REGISTRY[market_id]


def get_listing_sources(market_scope: str) -> tuple[str, ...]:
    return MARKET_REGISTRY[market_scope].listing_sources


def list_market_scopes() -> list[tuple[str, str]]:
    return [(market_id, MARKET_REGISTRY[market_id].label) for market_id in DEFAULT_MARKET_ORDER]
