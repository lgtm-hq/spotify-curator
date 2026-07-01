"""Session cost budget."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from app.ai.exceptions import AIError


@dataclass
class CostBudget:
    """Track cumulative AI cost."""

    max_cost_usd: float | None = None
    _spent: float = field(default=0.0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def record(self, cost: float) -> None:
        """Record cost increment."""
        with self._lock:
            self._spent += cost

    @property
    def spent(self) -> float:
        """Total spent."""
        with self._lock:
            return self._spent

    def check(self) -> None:
        """Raise if budget exceeded."""
        if self.max_cost_usd is not None and self.spent >= self.max_cost_usd:
            raise AIError(
                f"AI cost budget exceeded: ${self.spent:.4f} / ${self.max_cost_usd:.2f}",
            )
