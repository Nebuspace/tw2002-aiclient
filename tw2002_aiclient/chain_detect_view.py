"""chain_detect_view -- the pure formatter for class-derived pair loops.

Hub ruling (2026-07-28), replacing `chain_detect.as_library_rows`'s bridge
into `loops/list_view.format_loop_row`: a `chain_detect.PairLoopResult` is
not a taught macro -- it has no keystroke `steps[]`, no `start_anchor`, and
must claim neither `"recorded"` nor `"mined"` provenance. `format_loop_row`
was the wrong consumer, not a thing to repair; this module is the
dedicated replacement, with columns that mean what they show: sectors,
the compatible commodity sets each direction, round-trip turns, an
explicit provenance tag (`SOURCE_TAG`, never `"recorded"`/`"mined"`), and
an honest-unknown mark wherever a value is missing or malformed.

Pure: no filesystem, no session, no curses, no import of `chain_detect`,
`trade_adapter`, or anything under `tw2002_aiclient.session`/`adapters`.
`format_candidate_pair_lines`'s `payload` argument is read entirely by
`getattr(..., default)` -- exactly `cockpit/chains.py::compose_chain_lines`'s
own discipline -- so this function accepts a real `chain_detect.PairLoopResult`
or any duck-typed stand-in without ever importing that module to check.

# House pattern (matched, not re-invented)

Every sibling composer in `cockpit/` (`compose_chain_lines`, `panic.py`,
`armconfirm.py`, `autoloop_controls.py`) shares one hardening family: never
raises regardless of input shape, a malformed payload degrades to a
placeholder rather than an exception, and glyphs come from canon's table
with an ASCII twin gated on `unicode_ok`, never re-invented per-module.
This module is not itself IN `cockpit/` (that package is reserved for the
taught-macro/arm surfaces this feature must stay clearly apart from -- see
below), but it inherits that same discipline rather than drifting from it.

# Never the taught arm list (display is allowed; ARMING is not)

`cockpit/chains.py`'s `rows` are the ARM list (`app.py` -> `begin_arm_confirm`
-> `y` -> `adapters.autoloop_start`, the money-spending call). The bar is
ARMABILITY, not display: since WO-CHAINS-TUI-FULL the `L)chains` modal
displays discovered N-port cycles (`chain_search` results, via
`chain_search_view`) as a separate, `detected`-tagged, structurally
non-armable section. Pair loops have NO such display wire today -- this
module's rows reach the CLI listing only -- and if one lands it must take
the same shape: a section outside `rows`, never a row the cursor can select
or the arm path can receive. This module never imports `cockpit.chains`
(WO-CHAIN-DETECT-WIRE Accept 5, re-scoped 2026-07-28).

# The empty state -- deliberately NOT canon's `○ ○  no trade loop yet`

`canon/surfaces/visual-language.md`'s glyph table binds `○ ○` exclusively
to "the empty-chain placeholder" for **taught** loops (`chains.py`'s own
`EMPTY_UNICODE`/`EMPTY_TEXT`). A discovered-pairs empty is a different
fact -- "no compatible pairs" is not "no taught loop" -- and Samantha's
REVISE is explicit: an operator must never read one as the other. This
module's empty rendering uses `UNKNOWN` (`?`, itself canon no-swap and
already generically "an empty/unrecognized... reason code" per the glyph
table) plus wording drawn from `chain_detect`'s own five-reason vocabulary,
never `chains.EMPTY_UNICODE`/`chains.EMPTY_TEXT` and never their words.

# The `★`/`*` best-pair marker

`payload.pairs` arrives pre-ranked by `chain_detect.recompute` (round-trip
turns ascending). Row 0 is marked with canon's `★` (visual-language.md:
"centerpiece / you-are-here / chosen-action ... the longest Loops chain")
-- the same documented use-case, applied to this feature's own
cheapest/best discovered pair. Canon's table marks `★` no-swap, but `★`
(U+2605) is not ASCII either, the same gap Samantha already flagged for
`▸`/`○ ○` in `chains.py` (a genuine `TW2002_ASCII=1` terminal would get
mojibake) -- so this module gives it a real ASCII twin (`*`), following
the code's already-established precedent rather than canon's stale
no-swap claim. Do not "fix" canon here; that correction is Max-gated.
"""

from __future__ import annotations

from typing import Any

TITLE = "Discovered pair loops"

# Canon glyph vocabulary (canon/surfaces/visual-language.md §"Glyph /
# status-marker vocabulary"), defined LOCALLY -- this repo's own
# convention: `loops/list_view.py` and `cockpit/chains.py` each define
# these same literal characters locally rather than importing them
# cross-module. Canon itself, not any one Python module, is the single
# source of truth for the character; importing from `cockpit.chains`
# here would also re-couple this module to that package, which the
# "never the arm list" rule above deliberately avoids.
UNKNOWN = "?"  # no-swap (visual-language.md)

BEST_UNICODE = "★"
BEST_ASCII = "*"  # real ASCII twin -- see module docstring's ★/* note

# Per-row provenance tag -- never "recorded"/"mined" (`loops/store.py`'s
# `SOURCE_VALUES`; a `CandidatePair` was neither demonstrated at the
# keyboard nor ledger-mined). Width-pinned against `_SOURCE_TAG_MAX_W`
# below (a generous, deliberately-loose ceiling -- this column is
# reserved/never-truncated in `_format_one_pair`, same discipline as
# `turns_text`, so a future rename that blows the ceiling is caught here
# rather than silently eating another column's space at render time).
SOURCE_TAG = "detected"
_SOURCE_TAG_MAX_W = 12

# Deliberately distinct from `cockpit/chains.py`'s canon-bound
# `EMPTY_UNICODE`/`EMPTY_TEXT` -- see module docstring's "empty state"
# section. `UNKNOWN` doubles as the empty-state lead glyph; no ASCII twin
# is needed because `UNKNOWN` itself is already canon no-swap.
_REASON_TEXT = {
    "no_world_model": "world not yet explored",
    "fewer_than_two_ports": "fewer than 2 known ports",
    "all_stale": "class data too old",
    "no_compatible_pairs": "no compatible postures",
    "compatible_but_unrouted": "compatible pair, no known route yet",
}
_DEFAULT_EMPTY_TEXT = "no discovered pair loops"


def _sector_pair_text(sector_a: object, sector_b: object) -> str:
    a = str(sector_a) if isinstance(sector_a, int) and not isinstance(sector_a, bool) else UNKNOWN
    b = str(sector_b) if isinstance(sector_b, int) and not isinstance(sector_b, bool) else UNKNOWN
    return f"{a}<->{b}"


def _commodities_text(names: object) -> str:
    """A compatible commodity set, rendered whole -- never collapsed to
    one (see `trade_adapter.CandidatePair`'s own docstring for why a
    single-pick tiebreak was removed). Non-str / blank entries are
    dropped rather than crashing the join; an empty or unusable set
    renders `UNKNOWN`, never a bare empty string that could be mistaken
    for a rendering bug."""
    if not isinstance(names, (tuple, list)):
        return UNKNOWN
    clean = [n for n in names if isinstance(n, str) and n.strip()]
    if not clean:
        return UNKNOWN
    return ",".join(clean)


def _turns_text(turns: object) -> str:
    if isinstance(turns, bool) or not isinstance(turns, int) or turns < 0:
        return f"{UNKNOWN}t"
    return f"{turns}t"


def _format_one_pair(pair: object, *, index: int, best_marker: str, width: int) -> str:
    """One row. `turns_text` and `SOURCE_TAG` are computed and reserved
    FIRST and are never truncated: `turns` is the one genuinely-known,
    never-fabricated number on this row (`CandidatePair`'s own
    docstring), and `SOURCE_TAG` is the provenance mark that keeps this
    row from ever being mistaken for a taught macro -- both must survive
    regardless of how narrow `width` is. Only the descriptive body
    (sectors + commodity sets) is clipped to whatever space remains,
    the same "protect the count, clip the description" discipline
    `compose_chain_lines` uses for its own `steps_text`/`name`."""
    sector_a = getattr(pair, "sector_a", None)
    sector_b = getattr(pair, "sector_b", None)
    turns = getattr(pair, "turns", None)
    a_sells = getattr(pair, "commodities_a_sells", None)
    b_sells = getattr(pair, "commodities_b_sells", None)

    marker = f"{best_marker} " if index == 0 else "  "
    turns_text = _turns_text(turns)
    body = (
        f"{_sector_pair_text(sector_a, sector_b)}  "
        f"{_commodities_text(a_sells)} / {_commodities_text(b_sells)}"
    )

    reserved = len(turns_text) + 2 + len(SOURCE_TAG)
    avail = max(4, width - len(marker) - reserved)
    body = body[:avail]
    return f"{marker}{body:<{avail}}  {turns_text}  {SOURCE_TAG}"


def format_candidate_pair_lines(
    payload: Any,
    *,
    unicode_ok: bool = True,
    width: int = 40,
) -> list[str]:
    """The listing's body lines. Never raises regardless of `payload`'s
    shape -- a malformed or unrecognized-shape payload degrades to the
    honest-empty rendering rather than blowing up the draw pass, the
    same discipline `compose_chain_lines` documents for a malformed
    session.

    Reads `payload.pairs` / `.reason` / `.detail` by `getattr` (never
    `isinstance(payload, PairLoopResult)`), so a real
    `chain_detect.PairLoopResult` or any duck-typed stand-in both work
    identically -- this module never imports `chain_detect`.

    Row 0 (the cheapest/best pair -- `payload.pairs` arrives pre-ranked)
    is marked with `BEST_UNICODE`/`BEST_ASCII`, gated on `unicode_ok`.
    An empty result renders `TITLE` plus one honest-empty line drawn
    from `chain_detect`'s five-reason vocabulary -- see module
    docstring's "empty state" section for why this is never canon's
    `○ ○  no trade loop yet`.
    """
    try:
        w = int(width)
    except Exception:  # noqa: BLE001
        w = 40
    w = max(12, w)
    best = BEST_UNICODE if unicode_ok else BEST_ASCII

    pairs = getattr(payload, "pairs", None)
    if not isinstance(pairs, (tuple, list)) or not pairs:
        reason = getattr(payload, "reason", None)
        detail = getattr(payload, "detail", None)
        text = _REASON_TEXT.get(reason, _DEFAULT_EMPTY_TEXT)
        if isinstance(detail, str) and detail.strip():
            text = f"{text} ({detail.strip()})"
        return [TITLE, f"{UNKNOWN}  {text}"]

    lines = [TITLE]
    for i, pair in enumerate(pairs):
        lines.append(_format_one_pair(pair, index=i, best_marker=best, width=w))
    return lines
