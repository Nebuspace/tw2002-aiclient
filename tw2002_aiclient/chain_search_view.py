"""chain_search_view -- the pure formatter for DISCOVERED N-port profit cycles.

Sibling of `chain_detect_view` (which formats 2-port PAIR loops), same
discipline, one deliberate addition: **this listing can be partial, and it
has to say so.**

Pure: no filesystem, no session, no curses, no import of `chain_search`,
`chains`, `trade_adapter`, or anything under `tw2002_aiclient.session` /
`adapters`. `payload` is read entirely by `getattr(..., default)` -- exactly
`cockpit/chains.py::compose_chain_lines`'s discipline -- so a real
`chain_search.ProfitChainResult` or any duck-typed stand-in both work
without this module importing that one to check.

Inherits the sibling composers' hardening family: never raises regardless of
input shape, a malformed payload degrades to the honest-empty rendering
rather than blowing up a draw pass, ASCII twins gated on `unicode_ok`.

# Never the taught arm list (display is allowed; ARMING is not)

`cockpit/chains.py`'s `rows` are the ARM list (`app.py` -> `begin_arm_confirm`
-> `y` -> `adapters.autoloop_start`, the money-spending call). Since
WO-CHAINS-TUI-FULL the `L)chains` modal DISPLAYS discovered cycles —
`cockpit.chains.compose_chain_lines` calls THIS formatter for a separate,
`detected`-tagged, structurally non-armable section — but a discovered chain
never enters `rows`, the cursor never traverses it, and `selected()` / the
arm path cannot express one (a `ProfitChain` has no name, no `steps[]`, no
`start_anchor`; arming it would synthesise a macro the human never
demonstrated). The load-bearing invariant is **never armable**, not never
displayed. This module still never imports `cockpit.chains`; the dependency
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

TITLE = "Discovered profit chains"

UNKNOWN = "?"  # no-swap (visual-language.md)

BEST_UNICODE = "★"
BEST_ASCII = "*"  # real ASCII twin -- see `chain_detect_view`'s ★/* note

# Per-row provenance tag -- never "recorded"/"mined" (`loops/store.py`'s
# `SOURCE_VALUES`): a discovered cycle was neither demonstrated at the
# keyboard nor ledger-mined. Width-pinned so a rename that blows the
# ceiling is caught by a test rather than silently eating another column.
SOURCE_TAG = "detected"
_SOURCE_TAG_MAX_W = 12

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
    """Hop count = number of trade legs, the closed-set size that decides
    `chains.is_executable_chain`. Reserved and never truncated."""
    n = None
    if isinstance(hops, (tuple, list)):
        n = len(hops)
    if n is None or n < 0:
        return f"{UNKNOWN}h"
    return f"{n}h"


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


def _format_one_chain(chain: object, *, index: int, best_marker: str, width: int) -> str:
    """One row. `hops_text`, `cr_text` and `SOURCE_TAG` are computed and
    reserved FIRST and never truncated -- hop-count and cr/turn are the
    genuinely-known, never-fabricated numbers on this row, and the
    provenance tag is what keeps it from being read as a taught macro.
    Only the sector ring is clipped, the same "protect the count, clip the
    description" discipline `compose_chain_lines` uses."""
    marker = f"{best_marker} " if index == 0 else "  "
    hops_text = _hops_text(getattr(chain, "hops", None))
    turns_text = _turns_text(getattr(chain, "turns", None))
    cr_text = _cr_per_turn_text(getattr(chain, "cr_per_turn", None))
    body = _sectors_text(getattr(chain, "sectors", None))

    tail = f"{hops_text} {turns_text} {cr_text}"
    reserved = len(tail) + 2 + len(SOURCE_TAG)
    avail = max(4, width - len(marker) - reserved)
    body = body[:avail]
    return f"{marker}{body:<{avail}}  {tail}  {SOURCE_TAG}"


def format_profit_chain_lines(
    payload: Any,
    *,
    unicode_ok: bool = True,
    width: int = 48,
) -> list[str]:
    """The listing's body lines. Never raises regardless of `payload`'s shape.

    Reads `payload.chains` / `.reason` / `.detail` / `.adapter_note` /
    `.search_note` by `getattr` (never `isinstance`), so this module never
    imports `chain_search`.

    Row 0 (the best chain -- `payload.chains` arrives pre-ranked by
    `chains.rank_chains`) is marked with `BEST_UNICODE`/`BEST_ASCII`.

    A truncated result -- EITHER stage -- gets a `PARTIAL_*` banner, and a
    truncated EMPTY result says so rather than claiming absence.
    """
    try:
        w = int(width)
    except Exception:  # noqa: BLE001
        w = 48
    w = max(16, w)
    best = BEST_UNICODE if unicode_ok else BEST_ASCII
    partial_banner = PARTIAL_UNICODE if unicode_ok else PARTIAL_ASCII

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

    lines = [TITLE]
    if truncated:
        lines.append(partial_banner)
    for i, chain in enumerate(chains):
        lines.append(_format_one_chain(chain, index=i, best_marker=best, width=w))
    return lines
