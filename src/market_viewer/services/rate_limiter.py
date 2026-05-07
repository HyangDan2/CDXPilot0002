from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass(slots=True)
class AdaptiveRateLimiter:
    max_samples_per_second: float = 10.0
    min_samples_per_second: float = 1.0
    adaptive: bool = True
    error_count: int = 0
    success_streak: int = 0
    current_samples_per_second: float = 10.0
    adaptive_slowdown: bool = False
    _last_at: float = 0.0

    def __post_init__(self) -> None:
        self.max_samples_per_second = max(0.1, float(self.max_samples_per_second))
        self.min_samples_per_second = max(0.1, min(float(self.min_samples_per_second), self.max_samples_per_second))
        self.current_samples_per_second = self.max_samples_per_second

    def wait(self) -> None:
        interval = 1.0 / max(self.current_samples_per_second, 0.1)
        now = time.monotonic()
        if self._last_at:
            remaining = interval - (now - self._last_at)
            if remaining > 0:
                time.sleep(remaining)
        self._last_at = time.monotonic()

    def record_success(self) -> None:
        if not self.adaptive:
            return
        self.success_streak += 1
        if self.success_streak < 30:
            return
        self.success_streak = 0
        if self.current_samples_per_second < self.max_samples_per_second:
            self.current_samples_per_second = min(self.max_samples_per_second, self.current_samples_per_second * 1.5)
        self.adaptive_slowdown = self.current_samples_per_second < self.max_samples_per_second

    def record_error(self, exc: Exception) -> None:
        if not self.adaptive:
            return
        self.error_count += 1
        self.success_streak = 0
        message = str(exc).lower()
        aggressive = any(token in message for token in ("timeout", "time out", "429", "502", "503", "504"))
        if aggressive or self.error_count >= 6:
            target = max(self.min_samples_per_second, min(self.current_samples_per_second / 2.0, 2.0))
        elif self.error_count >= 3:
            target = max(self.min_samples_per_second, min(self.current_samples_per_second / 2.0, 5.0))
        else:
            return
        self.current_samples_per_second = target
        self.adaptive_slowdown = self.current_samples_per_second < self.max_samples_per_second
