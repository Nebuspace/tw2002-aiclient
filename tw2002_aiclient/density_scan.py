"""Density / holographic scan value-table parser (hypothesis grammar).

Canon: ``canon/engine/world-model.md`` — density values are cumulative
presence codes (approximately ``1=beacon · 5=fighter · 10=mine · 40=ship ·
100=port/StarDock · 500=planet``). This module extracts ``sector → density``
pairs from a rendered scan screen and offers provisional atom / fighter-
presence decoding for the writeback path.

It never sends keystrokes. Persistence lives in
:func:`tw2002_aiclient.world_model.write_density_scan` (always tagged
``HYPOTHESIS`` until a live multi-sector capture confirms the grammar).

The line grammar here is **provisional** (no live multi-sector density
screen is in the fixture corpus yet). Patterns are chosen to match common
TWGS density-scan phrasings and to fail closed on junk.
"""

from __future__ import annotations

import re
from typing import Mapping, Optional

# Canon target atoms (world-model.md). Cumulative: a reading of 105 may be
# port(100)+fighter(5). :func:`parse_density_scan` returns the raw integer;
# :func:`decode_density_atoms` is the provisional greedy decode.
DENSITY_VALUE_TABLE: Mapping[int, str] = {
    1: "beacon",
    5: "fighter",
    10: "mine",
    40: "ship",
    100: "port",
    500: "planet",
}

# Hypothesis row shapes (fail-closed — unmatched lines are ignored):
#   Sector  1234  Density:  105
#   Sector: 1234 Density = 105
#   Sector 1234 ==> Density 105
_SECTOR_DENSITY_RE = re.compile(
    r"(?i)\bsector\s*:?\s*(?P<sector>\d{1,5})\b"
    r".{0,40}?"
    r"\bdensity\s*(?:==>|:|=)?\s*(?P<density>\d{1,7})\b"
)

_ATOM_CODES_DESC = tuple(sorted(DENSITY_VALUE_TABLE.keys(), reverse=True))


def parse_density_scan(text: object) -> dict[int, int]:
    """Return ``{sector_id: density_value}`` from scan screen text.

    Last match wins per sector (same last-match discipline as CIM/report
    parsers). Non-string / empty input → ``{}``. Never raises.
    """
    if not isinstance(text, str) or not text:
        return {}
    out: dict[int, int] = {}
    try:
        for match in _SECTOR_DENSITY_RE.finditer(text):
            sector = int(match.group("sector"))
            density = int(match.group("density"))
            if sector <= 0 or density < 0:
                continue
            out[sector] = density
    except Exception:  # noqa: BLE001 -- fail-closed
        return {}
    return out


def decode_density_atoms(value: object) -> list[str]:
    """Greedy cumulative decode of a density integer → atom names.

    **HYPOTHESIS** — table + decode are provisional until a live capture
    confirms them. Non-int / negative → ``[]`` (fail-closed).
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return []
    remaining = value
    atoms: list[str] = []
    for code in _ATOM_CODES_DESC:
        name = DENSITY_VALUE_TABLE[code]
        while remaining >= code:
            atoms.append(name)
            remaining -= code
    return atoms


def fighter_presence_hypothesis(value: object) -> Optional[bool]:
    """Provisional fighter-presence signal from a density reading.

    - ``True`` when the greedy atom decode includes ``fighter``.
    - ``False`` when density is ``0`` (absence of the empty-sector reading
      implies no fighters — canon presence-via-absence, still HYPOTHESIS).
    - ``None`` when the reading is ambiguous (non-zero without a fighter
      atom) — callers must not invent a presence fact.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    if value == 0:
        return False
    if "fighter" in decode_density_atoms(value):
        return True
    return None
