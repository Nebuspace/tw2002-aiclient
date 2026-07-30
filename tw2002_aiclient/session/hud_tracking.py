"""Pure tracked-value types and strict cargo extraction for the HUD.

Cargo means *empty cargo holds*, matching the historical
``cargo_holds_empty`` HUD field. Two positive screen shapes are accepted:
the captured ``I`` ship-info line and the captured port-commerce sentence.
Everything else is a non-write; this module never guesses from total holds
or commodity rows.
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


def read_empty_cargo_holds(rendered_text: object) -> CargoRead:
    """Read empty holds from a settled screen; last positive match wins."""
    if not isinstance(rendered_text, str):
        return CargoRead(outcome=OUTCOME_UNREADABLE)

    found: list[tuple[int, int]] = []
    for match in _SHIP_INFO_EMPTY_RE.finditer(rendered_text):
        total = int(match.group(1).replace(",", ""))
        empty = int(match.group(2).replace(",", ""))
        # Impossible ship-info arithmetic is a damaged/partial claim, not a
        # value. Keep scanning in case a later complete line exists.
        if empty <= total:
            found.append((match.end(), empty))
    found.extend(
        (match.end(), int(match.group(1).replace(",", "")))
        for match in _PORT_EMPTY_RE.finditer(rendered_text)
    )
    if not found:
        return CargoRead(outcome=OUTCOME_ABSENT)
    found.sort(key=lambda item: item[0])
    return CargoRead(outcome=OUTCOME_READ, empty_holds=found[-1][1])


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

    def __post_init__(self) -> None:
        _validate_snapshot(self.outcome, self.cargo, self.age_s)


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
