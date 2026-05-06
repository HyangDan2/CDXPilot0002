# Current Status

## Active Scope

- Multi-market screener for `KOSPI`, `KOSDAQ`, and `KRX_ALL`
- Left pane: market selection, search, condition summary, screening progress, Stop button, and stock list
- Right pane: session summary/report tab and LLM prompt/result tab
- Separate chart window with candlestick and line views
- Menu-bar screening condition table based on the VSPilot0023 custom condition format
- Sequential stateless LLM report generation for completed screening results
- Per-stock user report and raw trace Markdown saved under `/log`
- Telegram text delivery for generated screening LLM reports
- YAML session save/load

## Recent Structural Changes

- The stock list was rebuilt from `QTableWidget` to a DataFrame-backed `QTableView` / `QAbstractTableModel` model.
- `KRX_ALL` list rendering no longer creates per-cell `QTableWidgetItem` objects.
- Worker signal emission now tolerates application teardown windows where the Qt signal object may already be deleted.
- LLM-based screening translation was removed. Screening conditions are local and hardcoded through the condition table.
- Legacy pykrx / FinanceDataReader financial fetching was removed, including KRX login and environment-variable paths.
- Kiwoom REST API is the primary data backend.
- `ka10099` powers listing, `ka10081` powers daily OHLCV, and `ka10001` powers basic information / financial snapshot metrics.
- The main UI was reduced to stock list and analysis panels; charts now live in a separate `ChartWindow`.
- `ChartWindow` is created lazily as a parentless top-level window when a chart is requested.
- Stock search handles Enter explicitly: numeric input resolves to a zero-padded six-digit code, then falls back to the current visible selection.
- `save_app_configs()` preserves existing YAML sections and writes Kiwoom appkey/secretkey under root `config.yaml > kiwoom`.
- `config.example.yaml` keeps only format/default values.
- Screening conditions save under `config.yaml > screening.custom_conditions`.
- Screening report options save under `config.yaml > screening`.
- `chart_panel.py` was replaced with a QtCharts-free QPainter renderer built on `QWidget.paintEvent()`.
- Candlestick, line, moving averages, volume overlay, bottom date labels, hover tooltip, pan, zoom, reset, and range persistence now run without `QtCharts.framework`.
- The chart X axis uses compressed trading-day indexing instead of real calendar spacing.
- Shutdown stops chart timers, clears pending chart work, clears the worker queue, and waits briefly for worker completion before close.

## Screening LLM Report Flow

- Manual trigger: `Screening > Generate/Send Screening LLM Reports`
- Auto trigger: `Screening > Auto-generate/send LLM reports after screening completion`
- Auto trigger is checkable and persists to `screening.auto_llm_reports`.
- Auto trigger validation requires both LLM connection settings and Telegram settings.
- Reports are generated sequentially, one stock at a time.
- Each stock report is stateless; previous stock reports are not reused as context.
- The user-facing Markdown report is saved to `log/{timestamp}_{code}_{safe_name}.md`.
- The raw trace is saved to `log/{timestamp}_{code}_{safe_name}_raw.md`.
- Run summary is saved to `log/{timestamp}_summary.md`.
- Telegram receives the report body as message text, not as a file attachment.
- Long Telegram messages are split into chunks by the Telegram client.

## Report Prompt Contract

The generated user report must include:

- Recent trading flow analysis
- Key evidence
- Trading-view approach recommendation
- Short-term view
- Long-term view
- Company fundamental analysis result
- Risks
- Overall judgement
- Legal-risk disclaimer and AI limitation notice

The prompt instructs the LLM not to invent absent data and to mark missing fields as unavailable.

## Current Module Set

- `src/market_viewer/analysis/condition_evaluator.py`
- `src/market_viewer/analysis/condition_parser.py`
- `src/market_viewer/analysis/filter_models.py`
- `src/market_viewer/analysis/stock_screener.py`
- `src/market_viewer/config/app_config_store.py`
- `src/market_viewer/data/kiwoom/client.py`
- `src/market_viewer/data/kiwoom/provider.py`
- `src/market_viewer/data/kiwoom/normalizers.py`
- `src/market_viewer/data/market_registry.py`
- `src/market_viewer/data/market_service.py`
- `src/market_viewer/services/context_service.py`
- `src/market_viewer/services/intelligence_service.py`
- `src/market_viewer/services/llm_service.py`
- `src/market_viewer/services/request_gate.py`
- `src/market_viewer/services/screening_report_service.py`
- `src/market_viewer/services/screening_service.py`
- `src/market_viewer/telegram/client.py`
- `src/market_viewer/ui/analysis_panel.py`
- `src/market_viewer/ui/chart_panel.py`
- `src/market_viewer/ui/chart_window.py`
- `src/market_viewer/ui/kiwoom_settings_dialog.py`
- `src/market_viewer/ui/llm_settings_dialog.py`
- `src/market_viewer/ui/main_window.py`
- `src/market_viewer/ui/screening_dialog.py`
- `src/market_viewer/ui/stock_list_panel.py`
- `src/market_viewer/ui/telegram_settings_dialog.py`
- `src/market_viewer/ui/worker.py`

## Removed Scope

- News/disclosure tab and related settings
- `OpenDART` / `Alpha Vantage` integration paths
- `FinanceDataReader` runtime dependency
- Legacy KRX login/environment-variable fundamental fetching
- LLM screening translator and screening schema modules
- QtCharts-based chart widget path

## Remaining Risks

- Repeated manual testing on resize, close, fast stock switching, and chart zoom/pan is still important because the chart renderer was replaced.
- Screening LLM report generation can be slow for many matched stocks because it intentionally runs sequentially to avoid rate-limit pressure.
- Telegram delivery depends on network availability and Telegram Bot API limits.
- Kiwoom `ka10001` provides a basic-information snapshot, not a full financial statement data model.
- `MainWindow` still owns most application orchestration and would benefit from controller extraction later.

## Suggested Next Checks

1. Launch the app and confirm it reaches the main window before any chart is opened.
2. Load `KOSDAQ` and `KRX_ALL`; confirm the stock list remains responsive.
3. Type a numeric code such as `005930` or `5930` in the stock search and press Enter; the separate chart window should update.
4. Open `Screening > Condition Settings`, edit a condition row, and apply it.
5. Run `Screening > Generate/Send Screening LLM Reports` after a screening result is visible.
6. Confirm `/log` contains user-facing, raw trace, and summary Markdown files.
7. Confirm Telegram receives report text, not file attachments.
8. Toggle auto report generation and confirm the setting persists in `config.yaml`.
