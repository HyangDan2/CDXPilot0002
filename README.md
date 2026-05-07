# Multi-Market Screener

PySide6 desktop application for Kiwoom REST based Korean equity screening, charting, local condition evaluation, LLM analysis, Telegram delivery, and session reporting.

Charts are displayed in a separate top-level window. The main UI stays focused on the stock list, screening workflow, and analysis/report panels.

## Features

- Kiwoom REST API listing for `KOSPI`, `KOSDAQ`, and `KRX_ALL`
- DataFrame-backed `QTableView` stock list for responsive large-list rendering
- Stock name/code search; pressing Enter activates the visible result and updates the chart window
- Menu-bar screening condition editor and local screening execution
- VSPilot0023-style condition table with price, volume, moving-average, and fundamental snapshot rules
- Screening progress with processed/total count, match count, failure count, percent, elapsed time, ETA, and Stop support
- Screening rate limiting starts at 10 samples/second and can automatically slow down after timeout or server errors
- Optional queued LLM report generation for completed screening results
- LLM stock reports are generated and sent one stock at a time, with a configurable 5-minute interval
- Optional in-app scheduler for hourly screening runs
- Per-stock Markdown report plus raw trace Markdown saved under `/log`
- LLM stock report retention keeps the latest 100 user-facing reports and removes older report/raw pairs
- Telegram text delivery for generated LLM reports; reports are sent as message text, not as file attachments
- Kiwoom `ka10001` basic-information snapshot for PER, PBR, ROE, EPS, BPS, revenue, operating profit, and net income
- Daily OHLCV chart data through Kiwoom `ka10081`
- Separate chart window with candlestick view, close line view, moving averages, volume overlay, pan, zoom, hover details, and range reset
- Trading-day compressed x-axis so weekends and market holidays do not render as blank gaps
- Session context Markdown, quantitative report table, LLM prompt/result panel, Telegram report delivery, and YAML session save/load

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If the local environment already has an older PySide build, reinstall the pinned runtime:

```bash
pip install --upgrade --force-reinstall PySide6==6.11.0 shiboken6==6.11.0
```

## Run

```bash
PYTHONPATH=src python -m market_viewer.main
```

## Configuration

Runtime secrets are stored in root `config.yaml`, which is not tracked by git. The repository keeps only `config.example.yaml` as a blank-format template.

```yaml
llm:
  base_url: "https://api.openai.com/v1"
  api_key: "YOUR_API_KEY_HERE"
  model: "gpt-4.1-mini"
  temperature: 0.2
  max_tokens: 12000
  timeout_seconds: 90

telegram:
  bot_token: "YOUR_TELEGRAM_BOT_TOKEN"
  chat_id: "YOUR_TELEGRAM_CHAT_ID"

kiwoom:
  enabled: false
  mock: false
  base_url: "https://api.kiwoom.com"
  mock_base_url: "https://mockapi.kiwoom.com"
  websocket_url: "wss://api.kiwoom.com:10000"
  mock_websocket_url: "wss://mockapi.kiwoom.com:10000"
  appkey: ""
  secretkey: ""
  token_cache_enabled: true

screening:
  auto_llm_reports: false
  telegram_after_llm_reports: true
  report_output_dir: "log"
  max_llm_report_stocks: 100
  max_llm_stock_reports: 100
  send_summary_to_telegram: true
  telegram_send_as_text: true
  max_samples_per_second: 10.0
  adaptive_speed_down: true
  min_samples_per_second: 1.0
  llm_report_queue_enabled: true
  llm_report_interval_minutes: 5
  scheduled_screening_enabled: false
  scheduled_screening_interval_minutes: 60
```

## Kiwoom REST

- `Market > Kiwoom REST Settings` saves Kiwoom REST credentials.
- `Market > Kiwoom REST Connection Test` issues a token and calls the KOSPI listing endpoint.
- Listing uses `ka10099`.
- Daily chart data uses `ka10081`.
- Basic information / financial snapshot data uses `ka10001`.
- Access tokens are kept in runtime memory and are not written to the config file.

## Screening Conditions

- Open `Screening > Condition Settings` to edit condition rows.
- Supported condition row fields include enabled state, name, `AND/OR`, MA ordering, MA comparisons, PER/PBR/ROE/EPS/BPS, revenue, operating profit, net income, market cap, foreign ownership ratio, volume, volume MA20, and volume ratio.
- Metric rule cells accept forms such as `<5`, `>10`, `>=0`, `<=100000`, and `>2,<10`.
- Run `Screening > Apply Conditions` to apply the active conditions to the current listing.
- Use the Stop button to stop after the current stock finishes processing.
- Screening uses a configurable rate limiter. The default rate is 10 samples/second.
- When adaptive slowdown is enabled, repeated timeout / 429 / 5xx / network errors reduce the scan speed down to the configured minimum.
- The progress label shows the current scan speed and marks automatic slowdown when it is active.

## Screening LLM Reports

The app can generate queued stateless LLM reports for the latest completed screening result.

Recommended workflow:

1. Run condition screening.
2. Review the matched list.
3. Run `Screening > Generate/Send Screening LLM Reports`.
4. The app enqueues up to `screening.max_llm_report_stocks` matched stocks.
5. The first stock is processed immediately; remaining stocks are processed one at a time every `screening.llm_report_interval_minutes`.
6. For each stock, it saves two Markdown files and sends the user-facing report to Telegram as plain message text.

Generated files:

- `log/{timestamp}_{code}_{safe_name}.md`: user-facing LLM analysis report
- `log/{timestamp}_{code}_{safe_name}_raw.md`: raw trace with input data, prompt, LLM output, Telegram result, and errors
- `log/{timestamp}_summary.md`: run-level summary

Retention:

- `screening.max_llm_stock_reports` controls how many user-facing stock reports are kept.
- When the count exceeds the limit, the oldest user-facing report is deleted with its matching `_raw.md` file.
- Summary files are not counted as stock reports.

The report prompt requires these sections:

- Recent trading flow analysis
- Key evidence
- Trading-view approach recommendation, split into short-term and long-term views
- Company fundamental analysis result
- Risks
- Overall judgement
- Legal-risk disclaimer and AI limitation notice

`Screening > Auto-generate/send LLM reports after screening completion` is a checkable menu toggle. It writes to `screening.auto_llm_reports`. When enabled, the app validates that LLM and Telegram settings are present before saving the toggle.

`Screening > Run scheduled screening every hour` is a checkable menu toggle. It writes to `screening.scheduled_screening_enabled`. The scheduler runs while the app is open and skips ticks when listing, screening, or report generation is already active.

`Screening > Report/Schedule Settings...` opens the report operations dialog. Saving the dialog updates `config.yaml > screening` immediately. If scheduled screening is enabled, the scheduler timer is restarted with the new interval.

Dialog fields:

- LLM report interval in minutes
- Scheduled screening interval in minutes
- Screening maximum speed in samples/second
- Adaptive minimum speed in samples/second
- Adaptive slowdown enabled/disabled
- Maximum queued report stocks
- Maximum stored stock reports
- LLM report queue enabled/disabled

## Telegram

- `Telegram > Telegram Settings`
- `Telegram > Send Session Report`
- `Telegram > Send LLM Result`

Screening LLM reports are sent as Telegram message text. They are not sent as Markdown file attachments. Long reports are split into multiple Telegram messages.

## LLM Notes

- The regular stock analysis panel uses the configured OpenAI-compatible `chat/completions` endpoint.
- Screening condition interpretation does not use the LLM.
- Screening LLM reports are stateless per stock: prior stock reports are not passed into the next stock prompt.
- Missing data must be reported as unavailable; the report prompt instructs the model not to infer absent data.
- The LLM response is expected to be Korean Markdown for user readability.

## Runtime Notes

- `PySide6` / `shiboken6` are pinned to `6.11.0`.
- Worker tasks compute plain Python data. Qt UI and chart state updates are routed back to the main GUI thread.
- The chart renderer is a `QWidget.paintEvent()` / QPainter implementation, not QtCharts.
- The stock list uses `QTableView + QAbstractTableModel`; it avoids creating thousands of `QTableWidgetItem` objects for large KRX lists.
- Shutdown stops chart timers, clears pending chart work, clears the worker queue, and waits briefly for worker completion.

## Status

The current implementation notes and risk list are tracked in [Current_Status.md](/Users/jaehyukshim/Documents/CODEX/CDXPilot0002/Current_Status.md).
