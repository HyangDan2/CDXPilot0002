# Current Status

## Active Scope

- Multi-market screener for `KOSPI`, `KOSDAQ`, and `KRX_ALL`
- Left pane: market selection, search, screened stock list
- Separate chart window: candlestick / line chart with pan, zoom, hover, and volume overlay
- Stock search activates the visible match on Enter and updates the chart window
- Right pane: session summary/report tab + LLM prompt/result tab
- Menu-bar screening condition dialog with hardcoded price/volume/fundamental snapshot rules
- Telegram report delivery
- YAML session save/load

## Recent Structural Changes

- The `뉴스 · 공시` tab and all related market-data configuration paths were removed.
- `OpenDART` / `Alpha Vantage` integration code was removed from the current app scope.
- `MainWindow` no longer owns news/disclosure refresh flows or market-data settings wiring.
- `PySide6` and `shiboken6` are now pinned to `6.11.0` as the target runtime, matching the latest PyPI release checked on 2026-05-01.
- Worker results are delivered through queued signal connections so UI slots always run on the main thread.
- LLM-based screening translation was removed. Screening now uses only local hardcoded conditions.
- Legacy pykrx/FinanceDataReader financial fetching was removed, including pykrx fundamental calls and KRX login/environment-variable paths.
- Kiwoom REST API backend was added as the primary data source.
- `ka10099` powers listing, `ka10081` powers daily OHLCV, and `ka10001` powers basic information / financial snapshot metrics.
- `FinanceDataReader` was removed from runtime dependencies.
- The main UI was reduced to stock list + analysis panels; charts now live in a separate `ChartWindow`.
- `ChartWindow` is now created lazily as a parentless top-level window when a chart is requested.
- Stock search now handles Enter explicitly: numeric input first resolves to a zero-padded six-digit code, then falls back to the current visible selection.
- Empty Kiwoom/unconfigured listings no longer break the search filter when the user types before data is loaded.
- `save_app_configs()` now preserves existing YAML sections and writes Kiwoom appkey/secretkey under root `config.yaml > kiwoom`; `config.example.yaml` keeps only blank-format values.
- `chart_panel.py` was replaced with a QtCharts-free QPainter renderer built on `QWidget.paintEvent()`.
- Candlestick, line, moving averages, volume overlay, bottom date labels, hover tooltip, pan, zoom, reset, and range persistence now run without `QtCharts.framework`.
- The chart X axis uses compressed trading-day indexing instead of real calendar spacing, so weekends and market holidays no longer render as empty gaps.
- Price updates replace plain Python chart state and request a repaint through `update()`.
- Shutdown now stops chart timers, clears pending chart work, clears the worker queue, and waits briefly for worker completion before close.

## Current Module Set

- `src/market_viewer/data/market_registry.py`
- `src/market_viewer/data/market_service.py`
- `src/market_viewer/data/kiwoom/client.py`
- `src/market_viewer/data/kiwoom/provider.py`
- `src/market_viewer/data/kiwoom/normalizers.py`
- `src/market_viewer/services/context_service.py`
- `src/market_viewer/services/intelligence_service.py`
- `src/market_viewer/services/llm_service.py`
- `src/market_viewer/services/request_gate.py`
- `src/market_viewer/services/screening_service.py`
- `src/market_viewer/ui/analysis_panel.py`
- `src/market_viewer/ui/chart_panel.py`
- `src/market_viewer/ui/chart_window.py`
- `src/market_viewer/ui/kiwoom_settings_dialog.py`
- `src/market_viewer/ui/main_window.py`
- `src/market_viewer/ui/screening_dialog.py`
- `src/market_viewer/ui/stock_list_panel.py`
- `src/market_viewer/ui/worker.py`

## Removed In This Pass

- `src/market_viewer/data/news_service.py`
- `src/market_viewer/data/disclosure_service.py`
- `src/market_viewer/services/intelligence_presenter.py`
- `src/market_viewer/ui/market_data_settings_dialog.py`
- `src/market_viewer/ui/widgets/feed_table.py`
- `src/market_viewer/data/fundamental_service.py`
- `src/market_viewer/llm/screening_translator.py`
- `src/market_viewer/llm/screening_schema.py`
- KRX Open API draft modules tied to fundamentals configuration

## Remaining Risks

- Repeated manual testing on resize, close, fast stock switching, and wheel zoom is still important because the chart renderer was replaced.
- `MainWindow` is lighter than before, but it still owns most application orchestration and would benefit from controller extraction later.

## Suggested Next Checks

1. Launch the app and confirm it reaches the main window before any chart is opened.
2. Type a numeric code such as `005930` or `5930` in the stock search and press Enter; the separate chart window should update.
3. Open `Screening > 조건 설정`, then apply each hardcoded preset.
4. Switch stocks repeatedly while panning/zooming both chart tabs.
5. Confirm `QtCharts.framework` no longer appears in the process crash report if any crash remains.
6. If crashes continue on `6.11.0`, inspect non-chart Qt object lifetime next, especially posted events during close/hide.
