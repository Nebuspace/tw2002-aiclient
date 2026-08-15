"""Working-capital ``trade_float`` on ``status`` — observe/merge only.

``cockpit/goals.py`` feeds ``afford_fighters`` from ``status["trade_float"]``.
Until this module, **nothing on tip wrote that key** — only tests injected it —
so discretionary math always treated the reserve as absent (same as 0).

**Honesty rules (canon priority-engine spending priority + vocab guard):**

- Never invent a tip default reserve (do not seed ``DEFAULT_CASH_FLOOR`` at
  play entry).
- ``merge`` contributes ``trade_float`` **only** after ``observe`` recorded a
  non-negative integer from an active money-path cash floor (or an explicit
  test inject).
- ``cash_floor`` on a live trade-chain / hold-buy run is the tip's known
  working-capital floor for that arm — observing it is not inventing a
  measured constant; omitting until that floor exists is fail-closed.
"""

from __future__ import annotations

__all__ = [
    "TradeFloatScalars",
    "TRADE_FLOAT_KEY",
]

TRADE_FLOAT_KEY = "trade_float"


class TradeFloatScalars:
    """Caches an observed working-capital reserve for status merge."""

    def __init__(self) -> None:
        self._trade_float: int | None = None

    def observe(self, trade_float: object) -> None:
        """Record a non-negative reserve; ignore bad values."""
        if isinstance(trade_float, bool) or not isinstance(trade_float, int):
            return
        if trade_float < 0:
            return
        self._trade_float = trade_float

    def clear(self) -> None:
        self._trade_float = None

    def merge(self, status: object) -> dict | None:
        """Attach cached key; never mutates input; never clobbers."""
        if not isinstance(status, dict):
            return status
        if self._trade_float is None:
            return status
        merged = dict(status)
        if merged.get(TRADE_FLOAT_KEY) is None:
            merged[TRADE_FLOAT_KEY] = self._trade_float
        return merged

    def wrap(self, provider):
        if provider is None:
            return None

        def _merged():
            return self.merge(provider())

        return _merged
