"""Pure tracked-value types and strict cargo extraction for the HUD.

Cargo sticky stores *empty cargo holds* (and, when ship-info states it,
*total holds*). Two positive screen shapes are accepted: the captured ``I``
ship-info line (``Total Holds : N - Empty=M``) and the captured port-commerce
sentence (empty only). Everything else is a non-write; this module never
guesses from commodity / market rows.

Per-commodity holdings (Fuel Ore / Organics / Equipment) are a separate
sticky model written only by verified trade buy/sell (or a future
ship-info parse). There is no fixture shape for per-commodity hold lines
yet — ``observe_holdings`` is intentionally a non-write. Market rows
never invent holdings.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional

from .state_parser import (
    OUTCOME_ABSENT,
    OUTCOME_READ,
    OUTCOME_UNREADABLE,
    OUTCOMES,
    SNAPSHOT_OUTCOMES,
)

_SHIP_INFO_EMPTY_RE = re.compile(
    r"^[ \t]*Total[ \t]+Holds[ \t]*:[ \t]*(\d[\d,]*)"
    r"[ \t]*-[ \t]*Empty[ \t]*=[ \t]*(\d[\d,]*)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
_PORT_EMPTY_RE = re.compile(
    r"^[ \t]*You[ \t]+have[ \t]+\d[\d,]*[ \t]+credits[ \t]+and[ \t]+"
    r"(\d[\d,]*)[ \t]+empty[ \t]+cargo[ \t]+holds\.[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class CargoRead:
    outcome: str
    empty_holds: Optional[int] = None
    total_holds: Optional[int] = None

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"invalid cargo outcome: {self.outcome!r}")
        read = self.outcome == OUTCOME_READ
        if read != (self.empty_holds is not None):
            raise ValueError("empty_holds accompanies exactly the read outcome")
        if self.empty_holds is not None and (
            isinstance(self.empty_holds, bool) or not isinstance(self.empty_holds, int)
        ):
            raise ValueError("empty_holds must be an int")
        if self.total_holds is not None:
            if not read:
                raise ValueError("total_holds only accompanies the read outcome")
            if isinstance(self.total_holds, bool) or not isinstance(
                self.total_holds, int
            ):
                raise ValueError("total_holds must be an int")
            if self.empty_holds is not None and self.empty_holds > self.total_holds:
                raise ValueError("empty_holds cannot exceed total_holds")


def read_empty_cargo_holds(rendered_text: object) -> CargoRead:
    """Read empty holds (and total when ship-info) from a settled screen.

    Last positive match wins for empty. Total is present only when that
    winning match was a ship-info line; port-commerce leaves total unset
    (session sticky may retain a prior ship-info total).
    """
    if not isinstance(rendered_text, str):
        return CargoRead(outcome=OUTCOME_UNREADABLE)

    found: list[tuple[int, int, Optional[int]]] = []
    for match in _SHIP_INFO_EMPTY_RE.finditer(rendered_text):
        total = int(match.group(1).replace(",", ""))
        empty = int(match.group(2).replace(",", ""))
        # Impossible ship-info arithmetic is a damaged/partial claim, not a
        # value. Keep scanning in case a later complete line exists.
        if empty <= total:
            found.append((match.end(), empty, total))
    for match in _PORT_EMPTY_RE.finditer(rendered_text):
        found.append((match.end(), int(match.group(1).replace(",", "")), None))
    if not found:
        return CargoRead(outcome=OUTCOME_ABSENT)
    found.sort(key=lambda item: item[0])
    _end, empty, total = found[-1]
    return CargoRead(outcome=OUTCOME_READ, empty_holds=empty, total_holds=total)


@dataclass(frozen=True)
class CargoHoldings:
    """Sticky Ore/Org/Equ quantities — unknown until first verified write."""

    fuel_ore: int = 0
    organics: int = 0
    equipment: int = 0

    def __post_init__(self) -> None:
        for name in ("fuel_ore", "organics", "equipment"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be an int >= 0")


_HOLDINGS_SHORT = (
    ("fuel_ore", "Ore"),
    ("organics", "Org"),
    ("equipment", "Equ"),
)

_COMMODITY_TO_HOLDINGS_FIELD = {
    "fuel ore": "fuel_ore",
    "organics": "organics",
    "equipment": "equipment",
}


def holdings_field_for_commodity(commodity: object) -> Optional[str]:
    """Map a hop commodity name to a CargoHoldings field, or None if unknown."""
    if not isinstance(commodity, str):
        return None
    return _COMMODITY_TO_HOLDINGS_FIELD.get(commodity.strip().casefold())


def format_cargo_hud_value(
    empty: int,
    total: Optional[int],
    holdings: Optional[CargoHoldings] = None,
) -> str:
    """Operator-honest CARGO cell: empty/total plus non-zero Ore/Org/Equ."""
    if total is None:
        base = f"{empty} empty"
    else:
        base = f"{empty} empty / {total}"
    if holdings is None:
        return base
    parts: list[str] = []
    for field, label in _HOLDINGS_SHORT:
        qty = getattr(holdings, field)
        if qty:
            parts.append(f"{label} {qty}")
    if not parts:
        return base
    return base + " · " + " · ".join(parts)


def _validate_snapshot(outcome: str, value: Optional[int], age_s: Optional[float]) -> None:
    if outcome not in SNAPSHOT_OUTCOMES:
        raise ValueError(f"invalid snapshot outcome: {outcome!r}")
    read = outcome == OUTCOME_READ
    if read != (value is not None) or read != (age_s is not None):
        raise ValueError("value and age accompany exactly the read outcome")
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
        raise ValueError("tracked HUD value must be an int")
    if age_s is not None:
        if isinstance(age_s, bool) or not isinstance(age_s, (int, float)):
            raise ValueError("age_s must be numeric")
        if not math.isfinite(age_s) or age_s < 0:
            raise ValueError("age_s must be finite and non-negative")


@dataclass(frozen=True)
class CargoSnapshot:
    outcome: str
    cargo: Optional[int] = None
    age_s: Optional[float] = None
    total_holds: Optional[int] = None
    holdings: Optional[CargoHoldings] = None

    def __post_init__(self) -> None:
        _validate_snapshot(self.outcome, self.cargo, self.age_s)
        if self.total_holds is not None:
            if self.outcome != OUTCOME_READ:
                raise ValueError("total_holds only accompanies the read outcome")
            if isinstance(self.total_holds, bool) or not isinstance(
                self.total_holds, int
            ):
                raise ValueError("total_holds must be an int")
            if self.cargo is not None and self.cargo > self.total_holds:
                raise ValueError("cargo empty cannot exceed total_holds")
        if self.holdings is not None:
            if self.outcome != OUTCOME_READ:
                raise ValueError("holdings only accompany the read outcome")
            if not isinstance(self.holdings, CargoHoldings):
                raise ValueError("holdings must be a CargoHoldings")


@dataclass(frozen=True)
class ProfitSnapshot:
    outcome: str
    profit: Optional[int] = None
    age_s: Optional[float] = None

    def __post_init__(self) -> None:
        _validate_snapshot(self.outcome, self.profit, self.age_s)


def cargo_never_observed() -> CargoSnapshot:
    return CargoSnapshot(outcome=OUTCOME_ABSENT)


def profit_never_observed() -> ProfitSnapshot:
    return ProfitSnapshot(outcome=OUTCOME_ABSENT)
