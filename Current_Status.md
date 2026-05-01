# Current Status

## Active Scope

- Multi-market screener for `KOSPI`, `KOSDAQ`, `TSE`, and `ALL`
- Left pane: market selection, search, natural-language screener
- Center pane: candlestick / line chart with pan, zoom, hover, and volume overlay
- Right pane: session summary/report tab + LLM prompt/result tab
- Telegram report delivery
- YAML session save/load

## Recent Structural Changes

- The `뉴스 · 공시` tab and all related market-data configuration paths were removed.
- `OpenDART` / `Alpha Vantage` integration code was removed from the current app scope.
- `MainWindow` no longer owns news/disclosure refresh flows or market-data settings wiring.
- `PySide6` and `shiboken6` are now pinned to `6.11.0` as the target runtime, matching the latest PyPI release checked on 2026-05-01.
- Worker results are delivered through queued signal connections so UI slots always run on the main thread.
- KOSPI / KOSDAQ fundamentals now use only `pykrx.get_market_fundamental(date, market=...)` with recent-date fallback, instead of mixing in the more brittle `get_market_fundamental_by_ticker()` path.
- Fundamental columns are normalized more defensively so `DIV`, `배당수익률`, `PER(배)` style variants can still populate the app's standard fields.
- `chart_panel.py` was reworked so `QChart`, `QLineSeries`, `QCandlestickSeries`, and axes are created once and stored as long-lived attributes.
- Chart updates no longer use `removeAllSeries()` or axis teardown/rebuild on every refresh.
- The chart X axis now uses compressed trading-day indexing instead of real calendar spacing, so weekends and market holidays no longer render as empty gaps.
- Price updates are batched through a main-thread `QTimer` flush path.
- Hover updates are also coalesced through a short main-thread timer to reduce event-loop churn around QtCharts repaint paths.
- Chart update code now includes a thread check plus a minimal debug log showing which thread applied the update.
- Shutdown now stops chart timers, clears pending chart work, clears the worker queue, and waits briefly for worker completion before close.

## Current Module Set

- `src/market_viewer/data/fundamental_service.py`
- `src/market_viewer/data/market_registry.py`
- `src/market_viewer/data/market_service.py`
- `src/market_viewer/services/context_service.py`
- `src/market_viewer/services/intelligence_service.py`
- `src/market_viewer/services/llm_service.py`
- `src/market_viewer/services/request_gate.py`
- `src/market_viewer/services/screening_service.py`
- `src/market_viewer/ui/analysis_panel.py`
- `src/market_viewer/ui/chart_panel.py`
- `src/market_viewer/ui/interactive_chart_view.py`
- `src/market_viewer/ui/main_window.py`
- `src/market_viewer/ui/stock_list_panel.py`
- `src/market_viewer/ui/worker.py`

## Removed In This Pass

- `src/market_viewer/data/news_service.py`
- `src/market_viewer/data/disclosure_service.py`
- `src/market_viewer/services/intelligence_presenter.py`
- `src/market_viewer/ui/market_data_settings_dialog.py`
- `src/market_viewer/ui/widgets/feed_table.py`

## Remaining Risks

- The biggest runtime risk remains QtCharts behavior on macOS ARM under heavier real-world interaction, even after moving updates to the GUI thread and stabilizing object ownership.
- `InteractiveChartView` hover/paint behavior is still event-heavy, so repeated manual testing on resize, close, fast stock switching, and wheel zoom is still important.
- `MainWindow` is cleaner than before, but it still owns most application orchestration and would benefit from controller extraction later.

## Suggested Next Checks

1. Launch the app and switch stocks repeatedly while panning/zooming both chart tabs.
2. Close the window during an active listing load and during an active price-history load.
3. Confirm the chart debug log always prints the main thread when updates apply.
4. If crashes continue on `6.11.0`, reduce repaint churn further by throttling or temporarily disabling hover crosshair repaint during rapid pan/zoom.
