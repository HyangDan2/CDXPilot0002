from __future__ import annotations

from market_viewer.models import MarketDefinition


MARKET_REGISTRY: dict[str, MarketDefinition] = {
    "KOSPI": MarketDefinition(
        id="KOSPI",
        label="KOSPI (코스피)",
        country="KR",
        currency="KRW",
        listing_sources=("KOSPI",),
    ),
    "KOSDAQ": MarketDefinition(
        id="KOSDAQ",
        label="KOSDAQ (코스닥)",
        country="KR",
        currency="KRW",
        listing_sources=("KOSDAQ",),
    ),
    "KRX_ALL": MarketDefinition(
        id="KRX_ALL",
        label="KRX ALL (코스피+코스닥)",
        country="KR",
        currency="KRW",
        listing_sources=("KOSPI", "KOSDAQ"),
    ),
}


DEFAULT_MARKET_ORDER = ["KOSPI", "KOSDAQ", "KRX_ALL"]


def get_market_definition(market_id: str) -> MarketDefinition:
    return MARKET_REGISTRY[market_id]


def get_listing_sources(market_scope: str) -> tuple[str, ...]:
    return MARKET_REGISTRY[market_scope].listing_sources


def list_market_scopes() -> list[tuple[str, str]]:
    return [(market_id, MARKET_REGISTRY[market_id].label) for market_id in DEFAULT_MARKET_ORDER]
