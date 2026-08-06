"""Density / holographic scan value-table parser (hypothesis grammar).

Canon: ``canon/engine/world-model.md`` — density values are cumulative
presence codes (approximately ``1=beacon · 5=fighter · 10=mine · 40=ship ·
100=port/StarDock · 500=planet``). This module extracts ``sector → density``
pairs from a rendered scan screen. It never sends keystrokes and never
writes the world model — ingestion/writeback is a later WO once a live
capture confirms the row grammar.

The line grammar here is **provisional** (no live multi-sector density
screen is in the fixture corpus yet). Patterns are chosen to match common
TWGS density-scan phrasings and to fail closed on junk.
"""

from __future__ import annotations

import re
from typing import Mapping

# Canon target atoms (world-model.md). Cumulative: a reading of 105 may be
# port(100)+fighter(5). This table is interpretive documentation for callers;
# :func:`parse_density_scan` returns the raw integer density, not a decoded set.
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
