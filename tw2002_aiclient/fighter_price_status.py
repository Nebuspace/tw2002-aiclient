"""Class-0 fighter unit-price on ``status`` — observe/merge only.

``cockpit/goals.py`` feeds ``afford_fighters`` from
``status["fighter_unit_price"]`` / ``status["fighter_price_class0"]``. Until
this module, **nothing on tip wrote either key** — only tests injected them
— so GOALS stayed at ``price?`` forever even after a real quote existed
elsewhere.

**Honesty rules (canon priority-engine + DECISIONS FIGHTER-UNIT-PRICE):**

- Never invent a tip ``FIGHTER_UNIT_PRICE_CLASS0`` measured constant.
- Never fall back to explore's ``FIGHTER_UNIT_PRICE_DEFAULT`` (routing-only).
- ``merge`` contributes keys **only** after ``observe`` recorded a positive
  integer from a captured/parsed screen (or an explicit test inject).
- Buy EXECUTE stays Max-gated and out of this module.

Live screen discovery is still open
(``canon/research/fighters-cargo-ship-purchase-coverage-2026-08-09.md`` —
StarDock reached, price line not found). Callers that later capture a quote
must ``observe`` it here; this module does not pretend a regex for an unseen
screen.
"""

from __future__ import annotations

__all__ = [
    "FighterPriceScalars",
    "UNIT_PRICE_KEY",
    "CLASS0_PRICE_KEY",
    "parse_fighter_unit_price",
]

import re

UNIT_PRICE_KEY = "fighter_unit_price"
CLASS0_PRICE_KEY = "fighter_price_class0"

# Provisional patterns for screens that *do* quote a unit price in plain text.
# Fail-closed: no match → None. Do not treat these as proof of any server's
# live menu — they only unlock parsing when such text is actually present.
_UNIT_PRICE_PATTERNS = (
    re.compile(
        r"Fighters?\s+cost\s+([\d,]+)\s+credits?\s+each",
        re.IGNORECASE,
    ),
    re.compile(
        r"([\d,]+)\s+credits?\s+(?:each|per)\s+fighter",
        re.IGNORECASE,
    ),
)


def parse_fighter_unit_price(text: object) -> int | None:
    """Extract a positive unit price from screen text, or ``None``.

    Never guesses. Unknown / empty / non-matching text → ``None``.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    for pat in _UNIT_PRICE_PATTERNS:
        match = pat.search(text)
        if match is None:
            continue
        try:
            n = int(match.group(1).replace(",", ""))
        except ValueError:
            continue
        if n > 0:
            return n
    return None


class FighterPriceScalars:
    """Caches an observed Class-0 unit price for status merge (display only)."""

    def __init__(self) -> None:
        self._unit_price: int | None = None

    def observe(self, unit_price: object) -> None:
        """Record a captured positive unit price; ignore bad values."""
        if isinstance(unit_price, bool) or not isinstance(unit_price, int):
            return
        if unit_price <= 0:
            return
        self._unit_price = unit_price

    def observe_screen(self, text: object) -> int | None:
        """Parse + observe when text carries a unit quote; return the price."""
        parsed = parse_fighter_unit_price(text)
        if parsed is not None:
            self.observe(parsed)
        return parsed

    def clear(self) -> None:
        self._unit_price = None

    def merge(self, status: object) -> dict | None:
        """Attach cached keys; never mutates input; never clobbers."""
        if not isinstance(status, dict):
            return status
        if self._unit_price is None:
            return status
        merged = dict(status)
        if merged.get(UNIT_PRICE_KEY) is None:
            merged[UNIT_PRICE_KEY] = self._unit_price
        if merged.get(CLASS0_PRICE_KEY) is None:
            merged[CLASS0_PRICE_KEY] = self._unit_price
        return merged

    def wrap(self, provider):
        if provider is None:
            return None

        def _merged():
            return self.merge(provider())

        return _merged
