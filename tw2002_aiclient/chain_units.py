"""Chain hop/step counting — the single place that decides which word applies.

A discovered trade loop and a recorded macro both arrive shaped as a library row
with the same ``steps`` wire field, but they mean different things: a trade loop
has **hops** along a sector path, a macro has **steps** in a keystroke sequence.
Conflating them puts a macro's step count under a "hops" label. This module is
the one place that decision is made.

Ported at the rebirth from pre-rebirth ``twclient/spectate_layout.py`` (deleted
by the ``452d896`` scaffold) per ``WO-COACH-ENGINE-PORT``. It lives here rather
than inside ``coach_engine`` because it is chain arithmetic that the coaching
engine merely *consumes* -- see the module note below.

**That gap is now closed** (``WO-STATUS-CHAIN-SCALARS-COACH``).
``cockpit/goals.py`` reads ``status["chain_hops"]`` / ``status["chain_unit"]``
to render the GOALS Chain row, and for one release **no product code wrote
either field** -- only tests did, which is why the suite was green while the
live row could only ever say "unknown". The pre-rebirth producer was
``spectate_app.py`` (deleted at the rebirth); the reborn one is
``chain_status.ChainScalars``, which calls ``chain_hop_count_and_unit`` below on
the ranked-first chain of a discovery and merges the result into ``status``.
"""

from __future__ import annotations

__all__ = [
    "chain_hop_count_and_unit",
    "hop_count_from_sectors",
    "unit_for_source",
]

# Sources whose "steps" really are sector hops along a discovered path.
_HOP_SOURCES = ("discovered", "presence_seed")


def unit_for_source(source: object) -> str:
    """``"hops"`` for a discovered trade loop or a presence-seed port path;
    ``"steps"`` for a recorded/mined skill macro.

    Both share the same ``steps`` wire field, so this is the one place that
    decides which word it actually means.
    """
    return "hops" if source in _HOP_SOURCES else "steps"


def hop_count_from_sectors(sectors: object) -> int | None:
    """Edge count along a sector path, or ``None`` when there is no path.

    A closed cycle ``a…a`` keeps its return hop, so edges are ``len(path) - 1``
    for both open and closed paths.
    """
    try:
        secs = [int(s) for s in (sectors or ())]
    except (TypeError, ValueError):
        return None
    if len(secs) < 2:
        return None
    return len(secs) - 1


def chain_hop_count_and_unit(chain: object) -> tuple[int | None, str]:
    """``(count, unit)`` for a chain-like value.

    ``chain`` may be a ProfitChain-like object with real ``.hops``, a
    "discovered" library-row dict (real hops, re-shaped), a presence-seed port
    path (``sectors``, no commodities yet), or a recorded/mined skill's library
    row (macro **steps**, not hops).

    ``count`` is ``None`` when there is nothing to show. ``unit`` falls back to
    ``"hops"`` when there is no dict to read a ``source`` from.
    """
    if chain is None:
        return None, "hops"

    hops = getattr(chain, "hops", None)
    if hops is not None:
        try:
            return len(hops), "hops"
        except TypeError:
            pass

    if isinstance(chain, dict):
        unit = unit_for_source(chain.get("source"))
        if chain.get("steps") is not None:
            try:
                count = int(chain["steps"]) or None
            except (TypeError, ValueError):
                count = None
            if count is not None:
                return count, unit
        # Presence seeds omit ``steps`` but still render a path, so derive the
        # hop count from ``sectors`` rather than reporting "none yet".
        count = hop_count_from_sectors(chain.get("sectors"))
        return count, unit if count is not None else "hops"

    if hasattr(chain, "sectors"):
        return hop_count_from_sectors(getattr(chain, "sectors", None)), "hops"

    return None, "hops"
