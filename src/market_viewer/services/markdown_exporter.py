from __future__ import annotations

from datetime import datetime

import pandas as pd

from market_viewer.analysis.filter_models import ParsedFilter


def build_screening_markdown(
    *,
    market_scope: str,
    parsed_filter: ParsedFilter,
    frame: pd.DataFrame,
    exported_at: datetime,
) -> str:
    condition_lines = [f"- {condition.label}" for condition in parsed_filter.conditions] or ["- 조건 없음"]
    warnings = [f"- {warning}" for warning in parsed_filter.warnings]

    lines = [
        "# Screening Export",
        "",
        f"- Exported At: {exported_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Market Scope: {market_scope}",
        f"- Query: {parsed_filter.normalized_prompt or parsed_filter.original_prompt or '없음'}",
        f"- Result Count: {len(frame)}",
        "",
        "## Conditions",
        *condition_lines,
    ]
    if warnings:
        lines.extend(["", "## Warnings", *warnings])

    lines.extend(["", "## Results", ""])
    if frame.empty:
        lines.append("No matched stocks.")
        return "\n".join(lines)

    columns = ["Market", "Code", "Name", "Close", "ChangePct", "Volume"]
    available = [column for column in columns if column in frame.columns]
    header = "| " + " | ".join(available) + " |"
    separator = "| " + " | ".join("---" for _ in available) + " |"
    lines.extend([header, separator])
    for _, row in frame.iterrows():
        values = []
        for column in available:
            value = row.get(column)
            if pd.isna(value):
                values.append("-")
            elif column in {"Close"}:
                values.append(f"{float(value):,.0f}")
            elif column in {"ChangePct"}:
                values.append(f"{float(value):.2f}")
            elif column in {"Volume"}:
                values.append(f"{float(value):,.0f}")
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)
