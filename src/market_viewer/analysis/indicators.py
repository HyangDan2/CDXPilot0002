from __future__ import annotations

import pandas as pd


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    enriched["MA5"] = enriched["Close"].rolling(5).mean()
    enriched["MA20"] = enriched["Close"].rolling(20).mean()
    enriched["MA60"] = enriched["Close"].rolling(60).mean()
    enriched["MA120"] = enriched["Close"].rolling(120).mean()
    enriched["VolumeMA20"] = enriched["Volume"].rolling(20).mean()
    enriched["VolumeRatio"] = enriched["Volume"] / enriched["VolumeMA20"].replace(0, pd.NA)
    for window in (5, 20, 60, 120):
        enriched[f"Return{window}D"] = enriched["Close"].pct_change(window) * 100
        enriched[f"High{window}D"] = enriched["High"].rolling(window).max()
        enriched[f"Low{window}D"] = enriched["Low"].rolling(window).min()

    delta = enriched["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, pd.NA)
    enriched["RSI14"] = 100 - (100 / (1 + rs))

    ema12 = enriched["Close"].ewm(span=12, adjust=False).mean()
    ema26 = enriched["Close"].ewm(span=26, adjust=False).mean()
    enriched["MACD"] = ema12 - ema26
    enriched["MACDSignal"] = enriched["MACD"].ewm(span=9, adjust=False).mean()
    enriched["MACDHist"] = enriched["MACD"] - enriched["MACDSignal"]
    return enriched
