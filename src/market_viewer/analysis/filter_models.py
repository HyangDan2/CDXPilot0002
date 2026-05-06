from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class FilterCondition:
    field: str
    operator: str
    value: object
    label: str


@dataclass(slots=True)
class ScreeningMetricRule:
    metric: str
    op: str
    value: float

    @property
    def label(self) -> str:
        return f"{self.metric} {self.op} {self.value:g}"


@dataclass(slots=True)
class ScreeningCondition:
    name: str
    enabled: bool = True
    operand: str = "AND"
    ma_order: list[int] = field(default_factory=list)
    ma_above: list[list[int]] = field(default_factory=list)
    metrics: list[ScreeningMetricRule] = field(default_factory=list)

    @property
    def active(self) -> bool:
        return bool(self.enabled and self.name.strip())

    @property
    def label(self) -> str:
        parts: list[str] = []
        if self.ma_order:
            parts.append("MA " + ">".join(str(value) for value in self.ma_order))
        for pair in self.ma_above:
            if len(pair) == 2:
                parts.append(f"MA{pair[0]}>MA{pair[1]}")
        parts.extend(rule.label for rule in self.metrics)
        body = f" {self.operand.upper()} ".join(parts) if parts else "조건 없음"
        return f"{self.name}: {body}"


@dataclass(slots=True)
class ScreeningProgress:
    done: int
    total: int
    matched: int
    failures: int
    current_code: str = ""
    current_name: str = ""
    elapsed_seconds: float = 0.0
    stopped: bool = False

    @property
    def percent(self) -> float:
        if self.total <= 0:
            return 0.0
        return min(100.0, max(0.0, (self.done / self.total) * 100))

    @property
    def remaining_seconds(self) -> float | None:
        if self.done <= 0 or self.elapsed_seconds <= 0:
            return None
        seconds_per_item = self.elapsed_seconds / self.done
        return max(0.0, (self.total - self.done) * seconds_per_item)


@dataclass(slots=True)
class ParsedFilter:
    original_prompt: str
    normalized_prompt: str
    markets: list[str] = field(default_factory=list)
    conditions: list[FilterCondition] = field(default_factory=list)
    custom_conditions: list[ScreeningCondition] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    resolution_source: str = "rule"

    @property
    def is_empty(self) -> bool:
        return not self.markets and not self.conditions and not self.custom_conditions and not self.original_prompt.strip()

    @property
    def can_apply(self) -> bool:
        return bool(self.original_prompt.strip() or self.markets or self.conditions or self.custom_conditions)
