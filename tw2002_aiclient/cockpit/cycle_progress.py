"""AUTO-LOOP cycle-progress chrome for the Play hint band
(WO-AUTOLOOP-CYCLE-PROGRESS).

Canon (``mode-line-and-teach-controls.md`` § hint band / AUTO-LOOP progress):

    Playing <name> ▸ cycle/total [███░░]

ASCII twin uses ``>`` and ``#`` / ``.``. Pure composer — no I/O, no invented
counts. Returns ``None`` when name/cycle/total are not a usable triple so
the surface omits the band rather than guessing.
"""

from __future__ import annotations

__all__ = [
    "BAR_WIDTH",
    "compose_cycle_progress",
]

#: Fixed fill width matching canon's ``[███░░]`` example.
BAR_WIDTH = 5

_SEP_UNICODE = "▸"
_SEP_ASCII = ">"
_FILL_UNICODE = "█"
_EMPTY_UNICODE = "░"
_FILL_ASCII = "#"
_EMPTY_ASCII = "."


def compose_cycle_progress(
    name: object,
    cycle: object,
    total: object,
    *,
    unicode_ok: object = True,
) -> str | None:
    """Canon cycle-progress string, or ``None`` when counts are unknown.

    ``cycle`` / ``total`` must be positive ints (bool rejected). ``cycle``
    may exceed ``total`` only if the wire lied — clamp fill to full bar,
    still render the raw numbers so the operator sees the mismatch.
    """
    if not isinstance(name, str) or not name.strip():
        return None
    if isinstance(cycle, bool) or not isinstance(cycle, int) or cycle < 1:
        return None
    if isinstance(total, bool) or not isinstance(total, int) or total < 1:
        return None

    use_unicode = bool(unicode_ok)
    sep = _SEP_UNICODE if use_unicode else _SEP_ASCII
    fill_ch = _FILL_UNICODE if use_unicode else _FILL_ASCII
    empty_ch = _EMPTY_UNICODE if use_unicode else _EMPTY_ASCII

    if cycle >= total:
        filled = BAR_WIDTH
    else:
        filled = int((cycle * BAR_WIDTH) // total)
        # A live pass that has begun must show at least one cell so the
        # bar is not an empty claim of "nothing playing".
        if filled < 1:
            filled = 1
    bar = fill_ch * filled + empty_ch * (BAR_WIDTH - filled)
    return f"Playing {name.strip()} {sep} {cycle}/{total} [{bar}]"
