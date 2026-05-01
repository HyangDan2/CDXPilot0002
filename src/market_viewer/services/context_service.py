from __future__ import annotations

import pandas as pd

from market_viewer.analysis.report_builder import build_stock_report, build_workspace_summary
from market_viewer.models import FundamentalSnapshot, LLMConfig, StockReference


def build_workspace_context_markdown(
    *,
    market_scope: str,
    stock: StockReference | None,
    filter_prompt: str,
    active_layer_names: list[str],
    llm_config: LLMConfig,
    chart_range_text: str,
    price_frame: pd.DataFrame | None,
    fundamental_snapshot: FundamentalSnapshot | None = None,
) -> str:
    summary = build_workspace_summary(
        market_scope=market_scope,
        stock=stock,
        filter_prompt=filter_prompt,
        active_layer_names=active_layer_names,
        llm_config=llm_config,
        chart_range_text=chart_range_text,
    )

    if stock is not None and price_frame is not None:
        report = build_stock_report(stock, price_frame, fundamental_snapshot)
        return summary + "\n\n" + report
    return summary + "\n\n선택된 종목이 아직 없습니다."
