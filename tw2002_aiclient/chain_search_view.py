"""chain_search_view -- the pure formatter for DISCOVERED N-port profit cycles.

Sibling of `chain_detect_view` (which formats 2-port PAIR loops), same
discipline, one deliberate addition: **this listing can be partial, and it
has to say so.**

Pure: no filesystem, no session, no curses, no import of `chain_search`,
`trade_adapter`, or anything under `tw2002_aiclient.session` /
`adapters`. Imports `chains.is_executable_chain` only — the execute-floor
helper that marks discovery-only short cycles (WO-WIRE-EXECUTABLE-CHAIN-VIEW).
`payload` is read entirely by `getattr(..., default)` -- exactly
`cockpit/chains.py::compose_chain_lines`'s discipline -- so a real
`chain_search.ProfitChainResult` or any duck-typed stand-in both work
without this module importing that one to check.

Inherits the sibling composers' hardening family: never raises regardless of
input shape, a malformed payload degrades to the honest-empty rendering
rather than blowing up a draw pass, ASCII twins gated on `unicode_ok`.

# Never the recorded-macro arm list

`cockpit/chains.py`'s `rows` are the ARM list (`app.py` -> `begin_arm_confirm`
-> `y` -> `adapters.autoloop_start`, the money-spending call). Since
WO-CHAINS-TUI-FULL the `L)chains` modal DISPLAYS discovered cycles —
`cockpit.chains.compose_chain_lines` calls THIS formatter for a separate,
`detected`-tagged section outside recorded ``rows``. ADR-003 permits a
different path: an exact discovered fingerprint may be selected, previewed,
and confirm-armed as a semantic one-pass trade plan. It never becomes a
recorded keystroke macro, and this formatter still has no arm or send path.
This module still never imports `cockpit.chains`; the dependency
points the other way. Ruling lineage: WO-CHAIN-DETECT-WIRE, re-scoped by
WO-CHAINS-TUI-FULL (hub, 2026-07-28).

# TRUNCATION IS PART OF THE RENDERING, not a footnote

`chain_search` carries two independent truncation notes -- the adapter's
edge cap and the finder's DFS budget. A partial listing that renders exactly
like an exhaustive one is a lie of omission at the only place the operator
actually looks. So:

* any truncation prepends a `PARTIAL_*` banner line, before the rows;
* an EMPTY result that was truncated says *"none found in the part searched"*,
  never a bare *"no profit chains"* -- because a truncated search has not
  established absence, only failed to find.

That second case is the sharp one. "There is no profitable cycle here" and
"I ran out of budget before finding one" are different facts about the
world, and only one of them is a reason to stop looking.
"""

from __future__ import annotations

from typing import Any

from tw2002_aiclient.chains import is_executable_chain

TITLE = "Discovered profit chains"

UNKNOWN = "?"  # no-swap (visual-language.md)

BEST_UNICODE = "★"
BEST_ASCII = "*"  # real ASCII twin -- see `chain_detect_view`'s ★/* note
SELECTED_UNICODE = "▸"
SELECTED_ASCII = ">"

# Per-row provenance tag -- never "recorded"/"mined" (`loops/store.py`'s
# `SOURCE_VALUES`): a discovered cycle was neither demonstrated at the
# keyboard nor ledger-mined. Width-pinned so a rename that blows the
# ceiling is caught by a test rather than silently eating another column.
SOURCE_TAG = "detected"
_SOURCE_TAG_MAX_W = 12

# Below `MIN_CHAIN_LINKS_TO_EXECUTE` — still shown, never dressed as an
# earn-macro candidate (WO-WIRE-EXECUTABLE-CHAIN-VIEW).
DISCOVERY_TAG = "discovery"

PARTIAL_UNICODE = "⚠ partial — search truncated"
PARTIAL_ASCII = "! partial - search truncated"

_REASON_TEXT = {
    "no_world_model": "world not yet explored",
    "no_tradeable_hops": "no priced, routable hops yet",
    "no_closed_cycle": "no closed profit cycle",
}
_DEFAULT_EMPTY_TEXT = "no discovered profit chains"

# Used ONLY when the empty result is also truncated. Deliberately not a
# suffix on the reason text above: this replaces the claim rather than
# decorating it, because the claim itself is what is unsafe.
_EMPTY_BUT_TRUNCATED_TEXT = "none found in the part searched (not exhaustive)"


def _int_or_none(value: object) -> int | None:
    """Bools are ints in Python and would render as 0/1 hop-counts."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _hops_text(hops: object) -> str:
    """Hop count = number of trade legs (same count `is_executable_chain`
    uses). Reserved and never truncated."""
    n = None
    if isinstance(hops, (tuple, list)):
        n = len(hops)
    if n is None or n < 0:
        return f"{UNKNOWN}h"
    return f"{n}h"


def _chain_is_executable(chain: object) -> bool:
    """True when the row clears the earn-macro floor; hostile shapes → True
    (do not falsely stamp discovery)."""
    try:
        return bool(is_executable_chain(chain))  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        return True


def _turns_text(turns: object) -> str:
    t = _int_or_none(turns)
    if t is None or t < 0:
        return f"{UNKNOWN}t"
    return f"{t}t"


def _sectors_text(sectors: object) -> str:
    """The closed cycle, rendered as its normalized ring. `chains.py`
    guarantees `sectors[0] == sectors[-1]`; the trailing repeat is dropped
    here because it is a representation detail, not information the
    operator needs twice."""
    if not isinstance(sectors, (tuple, list)) or not sectors:
        return UNKNOWN
    clean = [s for s in sectors if _int_or_none(s) is not None]
    if not clean:
        return UNKNOWN
    if len(clean) > 1 and clean[0] == clean[-1]:
        clean = clean[:-1]
    return ">".join(str(s) for s in clean) + ">"


def _cr_per_turn_text(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"{UNKNOWN}/t"
    return f"{value:.0f}/t"


def _format_one_chain(
    chain: object,
    *,
    marker: str,
    width: int,
    hold_count: int | None = None,
) -> str:
    """One row. `hops_text`, `cr_text` and `SOURCE_TAG` are computed and
    reserved FIRST and never truncated -- hop-count and cr/turn are the
    genuinely-known, never-fabricated numbers on this row, and the
    provenance tag is what keeps it from being read as a taught macro.
    Discovery-only (below-floor) rows append ``DISCOVERY_TAG``. Only the
    sector ring is clipped, the same "protect the count, clip the
    description" discipline `compose_chain_lines` uses.

    When ``hold_count`` is a positive int, the /t cell is *hold-scaled*
    trip EV (unit ``cr_per_turn`` × holds) so unit margins are not read as
    trip P&L. Ranking still uses the unit field. Unknown holds → unit /t.
    """
    from tw2002_aiclient.chains import hold_scaled_cr_per_turn

    marker_text = f"{marker} " if marker else "  "
    hops_text = _hops_text(getattr(chain, "hops", None))
    turns_text = _turns_text(getattr(chain, "turns", None))
    unit_cr = getattr(chain, "cr_per_turn", None)
    display_cr = unit_cr
    if hold_count is not None:
        scaled = hold_scaled_cr_per_turn(unit_cr, hold_count)
        if scaled is not None:
            display_cr = scaled
    cr_text = _cr_per_turn_text(display_cr)
    body = _sectors_text(getattr(chain, "sectors", None))
    discovery = f" {DISCOVERY_TAG}" if not _chain_is_executable(chain) else ""

    tail = f"{hops_text} {turns_text} {cr_text}"
    reserved = len(tail) + 2 + len(SOURCE_TAG) + len(discovery)
    avail = max(4, width - len(marker_text) - reserved)
    body = body[:avail]
    return f"{marker_text}{body:<{avail}}  {tail}  {SOURCE_TAG}{discovery}"


def format_profit_chain_lines(
    payload: Any,
    *,
    unicode_ok: bool = True,
    width: int = 48,
    selected_index: int | None = None,
    window_start: int = 0,
    window_size: int | None = None,
    hold_count: object = None,
) -> list[str]:
    """The listing's body lines. Never raises regardless of `payload`'s shape.

    Reads `payload.chains` / `.reason` / `.detail` / `.adapter_note` /
    `.search_note` by `getattr` (never `isinstance`), so this module never
    imports `chain_search`.

    Row 0 (the best chain -- `payload.chains` arrives pre-ranked by
    `chains.rank_chains`) is marked with `BEST_UNICODE`/`BEST_ASCII`.

    A truncated result -- EITHER stage -- gets a `PARTIAL_*` banner, and a
    truncated EMPTY result says so rather than claiming absence.

    ``window_size`` (optional): format only the slice starting at
    ``window_start``. When the full set exceeds the window, emit a
    ``showing N of M`` indicator and format only the visible rows (popup
    pagination — CLI callers leave ``window_size=None`` and see every row).

    ``hold_count`` (optional): positive ship holds. When known, /t cells
    show hold-scaled trip EV and a ``hold-scaled ×N`` banner is prepended
    so unit margins are not mistaken for trip P&L. Junk / missing → unit.
    """
    try:
        w = int(width)
    except Exception:  # noqa: BLE001
        w = 48
    w = max(16, w)
    best = BEST_UNICODE if unicode_ok else BEST_ASCII
    selected = SELECTED_UNICODE if unicode_ok else SELECTED_ASCII
    partial_banner = PARTIAL_UNICODE if unicode_ok else PARTIAL_ASCII

    holds: int | None = None
    if (
        hold_count is not None
        and not isinstance(hold_count, bool)
        and isinstance(hold_count, int)
        and hold_count > 0
    ):
        holds = hold_count

    # Computed by getattr, not via `payload.truncated`, so a duck-typed
    # stand-in without the property still renders honestly.
    truncated = (
        getattr(payload, "adapter_note", None) is not None
        or getattr(payload, "search_note", None) is not None
    )

    chains = getattr(payload, "chains", None)
    if not isinstance(chains, (tuple, list)) or not chains:
        if truncated:
            text = _EMPTY_BUT_TRUNCATED_TEXT
        else:
            reason = getattr(payload, "reason", None)
            text = _REASON_TEXT.get(reason, _DEFAULT_EMPTY_TEXT)
            detail = getattr(payload, "detail", None)
            if isinstance(detail, str) and detail.strip():
                text = f"{text} ({detail.strip()})"
        lines = [TITLE]
        if truncated:
            lines.append(partial_banner)
        lines.append(f"{UNKNOWN}  {text}")
        return lines

    total = len(chains)
    start = 0
    if not isinstance(window_start, bool) and isinstance(window_start, int):
        start = max(0, window_start)
    size: int | None = None
    if (
        window_size is not None
        and not isinstance(window_size, bool)
        and isinstance(window_size, int)
        and window_size >= 1
    ):
        size = window_size
    if size is None:
        start = 0
        end = total
        show_indicator = False
    else:
        start = min(start, max(0, total - 1))
        end = min(total, start + size)
        # Re-clamp start so a stale scroll never yields an empty window.
        if end - start < size and start > 0:
            start = max(0, end - size)
        show_indicator = total > size

    lines = [TITLE]
    if truncated:
        lines.append(partial_banner)
    if holds is not None:
        lines.append(f"hold-scaled ×{holds}")
    if show_indicator:
        # N = rows in this viewport; M = full discovered set.
        lines.append(f"showing {end - start} of {total}")
    for i in range(start, end):
        chain = chains[i]
        marker = selected if i == selected_index else (best if i == 0 else "")
        lines.append(
            _format_one_chain(
                chain,
                marker=marker,
                width=w,
                hold_count=holds,
            )
        )
    return lines
