from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class FilterCondition:
    field: str
    operator: str
    value: object
    label: str


@dataclass(slots=True)
class ParsedFilter:
    original_prompt: str
    normalized_prompt: str
    markets: list[str] = field(default_factory=list)
    conditions: list[FilterCondition] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    resolution_source: str = "rule"

    @property
    def is_empty(self) -> bool:
        return not self.markets and not self.conditions and not self.original_prompt.strip()

    @property
    def can_apply(self) -> bool:
        return bool(self.original_prompt.strip() or self.markets or self.conditions)
