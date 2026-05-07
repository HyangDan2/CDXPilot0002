from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
import time

import pandas as pd

from market_viewer.analysis.filter_models import ParsedFilter
from market_viewer.analysis.indicators import add_indicators
from market_viewer.data.market_service import MarketService
from market_viewer.llm.client import send_chat_completion
from market_viewer.models import LLMConfig, ScreeningReportConfig, StockReference, TelegramConfig
from market_viewer.telegram.client import send_telegram_report


@dataclass(slots=True)
class StockReportResult:
    stock: StockReference
    report_path: Path | None = None
    raw_path: Path | None = None
    telegram_chunks: int = 0
    error: str = ""

    @property
    def success(self) -> bool:
        return bool(self.report_path and not self.error)


@dataclass(slots=True)
class ScreeningReportSummary:
    timestamp: str
    output_dir: Path
    summary_path: Path
    matched: int
    report_cap: int
    total: int
    processed: int
    saved: int
    telegram_sent: int
    failures: int
    stopped: bool
    deleted_old_reports: int = 0
    results: list[StockReportResult] = field(default_factory=list)


def generate_screening_llm_reports(
    *,
    market_service: MarketService,
    llm_config: LLMConfig,
    telegram_config: TelegramConfig,
    report_config: ScreeningReportConfig,
    matched_listing: pd.DataFrame,
    parsed_filter: ParsedFilter,
    progress_callback=None,
    cancel_checker=None,
) -> ScreeningReportSummary:
    if not llm_config.connection_ready:
        raise ValueError("LLM connection settings are required before generating screening reports.")
    if report_config.telegram_after_llm_reports and not telegram_config.connection_ready:
        raise ValueError("Telegram Bot Token and Chat ID are required before sending screening reports.")

    root = Path(__file__).resolve().parents[3]
    output_dir = _resolve_output_dir(root, report_config.report_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_cap = max(1, report_config.max_llm_report_stocks)
    total = min(len(matched_listing), report_cap)
    results: list[StockReportResult] = []
    started_at = time.monotonic()
    stopped = False

    for index, (_, row) in enumerate(matched_listing.head(total).iterrows(), start=1):
        stock = market_service.build_stock_reference(row)
        if cancel_checker is not None and cancel_checker():
            stopped = True
            _emit_progress(progress_callback, index - 1, total, stock, results, started_at, stopped=True)
            break
        _emit_progress(progress_callback, index - 1, total, stock, results, started_at, stage="collect")
        result = _generate_single_report(
            market_service=market_service,
            llm_config=llm_config,
            telegram_config=telegram_config,
            report_config=report_config,
            output_dir=output_dir,
            timestamp=timestamp,
            stock=stock,
            listing_row=row,
            parsed_filter=parsed_filter,
        )
        results.append(result)
        _emit_progress(progress_callback, index, total, stock, results, started_at, stage="done")

    summary_path = output_dir / f"{timestamp}_summary.md"
    summary = ScreeningReportSummary(
        timestamp=timestamp,
        output_dir=output_dir,
        summary_path=summary_path,
        matched=len(matched_listing),
        report_cap=report_cap,
        total=total,
        processed=len(results),
        saved=sum(1 for result in results if result.report_path is not None),
        telegram_sent=sum(1 for result in results if result.telegram_chunks > 0),
        failures=sum(1 for result in results if result.error),
        stopped=stopped,
        deleted_old_reports=cleanup_old_stock_reports(output_dir, report_config.max_llm_stock_reports),
        results=results,
    )
    summary_text = _build_summary_markdown(summary)
    summary_path.write_text(summary_text, encoding="utf-8")
    if report_config.telegram_after_llm_reports and report_config.send_summary_to_telegram:
        try:
            send_telegram_report(telegram_config, "Screening LLM Report Summary", summary_text)
        except Exception:
            pass
    return summary


def cleanup_old_stock_reports(output_dir: Path, max_reports: int) -> int:
    max_reports = max(1, int(max_reports))
    report_files = sorted(
        (
            path
            for path in output_dir.glob("*.md")
            if not path.name.endswith("_raw.md") and not path.name.endswith("_summary.md")
        ),
        key=lambda path: path.stat().st_mtime,
    )
    excess = max(0, len(report_files) - max_reports)
    deleted = 0
    for report_path in report_files[:excess]:
        raw_path = report_path.with_name(report_path.stem + "_raw.md")
        for path in (report_path, raw_path):
            try:
                if path.exists():
                    path.unlink()
                    deleted += 1
            except OSError:
                continue
    return deleted


def _generate_single_report(
    *,
    market_service: MarketService,
    llm_config: LLMConfig,
    telegram_config: TelegramConfig,
    report_config: ScreeningReportConfig,
    output_dir: Path,
    timestamp: str,
    stock: StockReference,
    listing_row: pd.Series,
    parsed_filter: ParsedFilter,
) -> StockReportResult:
    safe_name = _safe_filename(stock.name)
    base_name = f"{timestamp}_{stock.code}_{safe_name}"
    report_path = output_dir / f"{base_name}.md"
    raw_path = output_dir / f"{base_name}_raw.md"
    result = StockReportResult(stock=stock, report_path=report_path, raw_path=raw_path)
    prompt = ""
    report_text = ""
    input_markdown = ""
    telegram_error = ""
    try:
        frame = add_indicators(market_service.load_price_history(stock, months=18))
        snapshot = market_service.load_fundamental_snapshot(stock)
        input_markdown = _build_input_markdown(stock, listing_row, frame, snapshot.values, parsed_filter)
        system_prompt = _build_system_prompt()
        prompt = _build_user_prompt(input_markdown)
        report_text = send_chat_completion(llm_config, system_prompt, prompt).strip()
        if not report_text:
            raise ValueError("LLM returned an empty report.")
        report_path.write_text(report_text, encoding="utf-8")
        if report_config.telegram_after_llm_reports:
            try:
                result.telegram_chunks = send_telegram_report(
                    telegram_config,
                    f"{stock.name}({stock.code}) Screening LLM Report",
                    report_text,
                )
            except Exception as exc:
                telegram_error = str(exc)
                result.error = f"Telegram send failed: {telegram_error}"
    except Exception as exc:
        result.error = result.error or str(exc)
        report_text = _build_failure_report(stock, result.error)
        report_path.write_text(report_text, encoding="utf-8")
    raw_path.write_text(
        _build_raw_markdown(
            stock=stock,
            input_markdown=input_markdown,
            prompt=prompt,
            report_text=report_text,
            telegram_chunks=result.telegram_chunks,
            telegram_error=telegram_error,
            error=result.error,
        ),
        encoding="utf-8",
    )
    return result


def _build_system_prompt() -> str:
    return (
        "You are a Korean stock analysis report writer. "
        "Generate a stateless report for exactly one stock. "
        "Do not use prior stock reports as context. "
        "Do not invent missing data. If data is absent, write '데이터 미제공'. "
        "The output must be Korean Markdown and must include every requested section."
    )


def _build_user_prompt(input_markdown: str) -> str:
    return f"""아래 입력 데이터만 사용해서 종목별 stateless 분석 보고서를 작성하라.

필수 출력 형식:

# {{종목명}}({{종목코드}}) 종목 분석 보고서

## 최근 매매동향 분석

## 핵심 근거
- 가격/추세 근거
- 거래량 근거
- 이동평균/기술적 근거
- 재무/기초체력 근거
- 스크리닝 조건 통과 근거

## 매매관점 접근 추천
### 단기 관점
### 장기 관점

## 회사 기초분석 결과

## 리스크

## 종합적 판단 결과

## 고지
- 본 보고서는 AI가 생성한 참고용 분석입니다.
- 투자 권유가 아니며, 실제 투자 판단과 책임은 사용자에게 있습니다.
- 제공 데이터와 AI 판단에는 오류, 지연, 누락이 있을 수 있습니다.

작성 규칙:
- 각 섹션 제목을 생략하지 말 것.
- 없는 데이터는 추정하지 말고 "데이터 미제공"이라고 쓸 것.
- 종합적 판단은 과도하게 단정하지 말고 조건부/확률적 표현을 사용할 것.
- 법적 리스크 회피 문구와 AI 생성 한계 고지를 반드시 포함할 것.

입력 데이터:

{input_markdown}
"""


def _build_input_markdown(
    stock: StockReference,
    listing_row: pd.Series,
    frame: pd.DataFrame,
    fundamentals: dict[str, object],
    parsed_filter: ParsedFilter,
) -> str:
    latest = frame.iloc[-1] if not frame.empty else pd.Series(dtype=object)
    previous = frame.iloc[-2] if len(frame) > 1 else latest
    return20 = _value(latest.get("Return20D"))
    volume_ratio = _value(latest.get("VolumeRatio"))
    condition_lines = "\n".join(
        f"- {condition.label}" for condition in parsed_filter.custom_conditions if condition.active
    ) or "- No active custom condition details."
    return f"""## Stock
- Name: {stock.name}
- Code: {stock.code}
- Market: {stock.market}
- Currency: {stock.currency}

## Screening Conditions
{condition_lines}

## Latest Trading Data
- Date: {_value(latest.get("Date"))}
- Close: {_value(latest.get("Close"))}
- Previous close: {_value(previous.get("Close"))}
- Daily change percent: {_value(listing_row.get("ChangePct"))}
- Volume: {_value(latest.get("Volume"))}
- Volume MA20: {_value(latest.get("VolumeMA20"))}
- Volume ratio: {volume_ratio}
- 20-day return: {return20}

## Moving Averages / Indicators
- MA5: {_value(latest.get("MA5"))}
- MA20: {_value(latest.get("MA20"))}
- MA60: {_value(latest.get("MA60"))}
- MA120: {_value(latest.get("MA120"))}
- MA224: {_value(latest.get("MA224"))}
- RSI14: {_value(latest.get("RSI14"))}
- MACD: {_value(latest.get("MACD"))}
- MACDSignal: {_value(latest.get("MACDSignal"))}

## Fundamental Snapshot
{_format_mapping(fundamentals)}
"""


def _build_failure_report(stock: StockReference, error: str) -> str:
    return f"""# {stock.name}({stock.code}) 종목 분석 보고서

## 최근 매매동향 분석
데이터 미제공

## 핵심 근거
- 보고서 생성 실패: {error}

## 매매관점 접근 추천
### 단기 관점
데이터 미제공
### 장기 관점
데이터 미제공

## 회사 기초분석 결과
데이터 미제공

## 리스크
- LLM 보고서 생성 또는 데이터 수집 중 오류가 발생했습니다.

## 종합적 판단 결과
데이터 미제공

## 고지
- 본 보고서는 AI가 생성한 참고용 분석입니다.
- 투자 권유가 아니며, 실제 투자 판단과 책임은 사용자에게 있습니다.
- 제공 데이터와 AI 판단에는 오류, 지연, 누락이 있을 수 있습니다.
"""


def _build_raw_markdown(
    *,
    stock: StockReference,
    input_markdown: str,
    prompt: str,
    report_text: str,
    telegram_chunks: int,
    telegram_error: str,
    error: str,
) -> str:
    return f"""# Raw Screening LLM Report Trace

## Stock
- Name: {stock.name}
- Code: {stock.code}
- Market: {stock.market}

## Status
- Error: {error or "None"}
- Telegram chunks sent: {telegram_chunks}
- Telegram error: {telegram_error or "None"}

## Input Data
{input_markdown or "No input data captured."}

## Prompt
```text
{prompt or "No prompt captured."}
```

## LLM Report
{report_text or "No report captured."}
"""


def _build_summary_markdown(summary: ScreeningReportSummary) -> str:
    lines = [
        "# Screening LLM Report Summary",
        "",
        f"- Timestamp: {summary.timestamp}",
        f"- Output directory: {summary.output_dir}",
        f"- Matched stocks: {summary.matched}",
        f"- Report cap: {summary.report_cap}",
        f"- Total target stocks: {summary.total}",
        f"- Processed: {summary.processed}",
        f"- Saved reports: {summary.saved}",
        f"- Telegram sent: {summary.telegram_sent}",
        f"- Failures: {summary.failures}",
        f"- Stopped: {summary.stopped}",
        f"- Deleted old report files: {summary.deleted_old_reports}",
        "",
        "## Files",
    ]
    for result in summary.results:
        status = "failed" if result.error else "ok"
        lines.append(
            f"- {result.stock.name}({result.stock.code}) [{status}] "
            f"report={result.report_path or '-'} raw={result.raw_path or '-'} telegram_chunks={result.telegram_chunks}"
        )
        if result.error:
            lines.append(f"  - error: {result.error}")
    return "\n".join(lines).strip() + "\n"


def _emit_progress(progress_callback, done: int, total: int, stock: StockReference, results: list[StockReportResult], started_at: float, stage: str = "run", stopped: bool = False) -> None:
    if progress_callback is None:
        return
    progress_callback(
        {
            "stage": stage,
            "done": done,
            "total": total,
            "saved": sum(1 for result in results if result.report_path is not None),
            "telegram_sent": sum(1 for result in results if result.telegram_chunks > 0),
            "failures": sum(1 for result in results if result.error),
            "current_code": stock.code,
            "current_name": stock.name,
            "elapsed_seconds": time.monotonic() - started_at,
            "stopped": stopped,
        }
    )


def _resolve_output_dir(root: Path, configured: str) -> Path:
    path = Path(configured or "log")
    if path.is_absolute():
        return path
    return root / path


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w가-힣.-]+", "_", value.strip(), flags=re.UNICODE)
    cleaned = cleaned.strip("._")
    return cleaned or "stock"


def _format_mapping(values: dict[str, object]) -> str:
    if not values:
        return "- 데이터 미제공"
    return "\n".join(f"- {key}: {_value(value)}" for key, value in sorted(values.items()))


def _value(value: object) -> str:
    if value is None:
        return "데이터 미제공"
    try:
        if pd.isna(value):
            return "데이터 미제공"
    except (TypeError, ValueError):
        pass
    if isinstance(value, float):
        return f"{value:,.4g}"
    return str(value)
