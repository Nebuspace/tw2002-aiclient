"""The standing calm teach hint band on the control strip (WO-P5-066;
redefined for the trainer surface by WO-PLAY-STRIP-TRAINER-CHROME per
DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 2).

# What this is now

The developer-repertoire band this module used to emit (`A)nalyze
R)ecord T)rigger V)reflex U)rules H)old? O)ffer? L)chains P panic`) is
**retired from this calm band** by Max's ratified DECISION -- the
underlying features (Record, Assign-Trigger, Analyze, reflex, rules
library, the hold/offer confirm gates, the chains popup, panic) are all
UNCHANGED and still reachable by their existing keys; only the standing
CHROME that advertises them on the calm strip changes, in favor of a
trainer-plain vocabulary:

    E)xplore  P)ort Trade·ON  L)oops  T)rade Loop Chain
    C)argo Hold Upgrade·ON  S)hip Upgrade·ON

- `E)xplore` reuses `autonomy_keys.EXPLORE_TOKEN` verbatim -- same key,
  same word, already trainer-plain.
- `L)oops` is a RELABEL of the same `L` key `chains.CHAINS_TOKEN`
  ("L)chains") already opens -- this module does not import or change
  `CHAINS_TOKEN` (other surfaces still cite the popup by that name); it
  is a local, calm-band-only spelling of the identical affordance.
- `T)rade Loop Chain` is a RELABEL of the same `T` key the old
  `T)rigger` token named (`screens.py`'s `assign_trigger` intent,
  WO-P5-068) -- trainer wording for the same wire, not a new one.
- `P)ort Trade`, `C)argo Hold Upgrade`, `S)hip Upgrade` are NEW
  chrome-only toggles (WO-PLAY-STRIP-TRAINER-CHROME): each renders
  `·ON`/`·OFF` from a caller-supplied boolean (default **ON**, per
  DECISION), driven by `PlayShellScreen`'s own local Play state. They are
  **display-only in this WO** -- no key is bound to flip them yet (`P` in
  particular stays bound to `cockpit.panic`'s existing handler; giving it
  a second, conflicting meaning here would be worse than an inert label).
  A key wire lands in a follow-on WO once the daemon side exists to back
  it; until then this is intentionally an honest "the label exists, the
  toggle is local paint" state, the same kind of WO-scoped intermediate
  `A`/`R`/`T` were during their own pre-wire days (see history below).

The STOP banner's own `teach:` line (`cockpit.stopbanner.TEACH_LINE`,
`A)nalyze R)ecord T)assign`) is a DIFFERENT register/surface entirely and
is untouched by this WO -- it names the same underlying Record/Trigger
affordances at the moment of a halt, in the developer spelling canon's
escalation banner still uses. This module never imported `TEACH_LINE`
before and still does not.

# History (why the old band's shape looked the way it did)

Kept for context, not because any of it still ships: the pre-trainer band
was built up WO-by-WO (`P5-066` A/R/T triad -> `P5-071` panic ->
`PLAY-REFLEX-AFFORDANCE`/`PLAY-RULES-LIBRARY` V/U ->
`PLAY-HELP-AUTONOMY-KEYS` H/O -> `TEACHBAND-L-CHAINS` L)chains), each
tracking the label a real key handler had just gained, exactly the
"advertise a key, wire it later" posture the trainer's own P/C/S toggles
now reuse for a different repertoire.

# Rendering contract

Plain strings and a tone NAME only; attribute resolution belongs to the
draw layer (`screens.py::_control_strip_segment_attr`), the same split
`arm.py` documents. The tone is `TEACH_TONE` -- canon: the hint band is
"right-aligned in **cyan** (`accent_attr`), the chrome accent -- it is
affordance chrome, not data" (`:229-231`), which is why it resolves to
the chrome attr rather than through the `ok`/`warn` badge path that the
seat and ARM chips use. It is chrome, so it is never reverse-video: the
badge treatment is canon's "selected/active" signal (`:179-181`) and this
band is neither.

`unicode_ok` is accepted for API uniformity with every sibling composer
in this package but has no effect: `visual-language.md §"Glyph / status-marker vocabulary"` lists
`KEY)verb` -> `KEY)verb` **(no swap)**, so the tokens are pure ASCII with
no Unicode twin to trade away on an 80-col non-UTF-8 terminal.

Hardening family (matches `arm.py`/`control_seat.py`/`stopbanner.py`):
never raises regardless of any argument's type or content.
"""

from __future__ import annotations

# `EXPLORE_TOKEN` is imported rather than re-spelled -- the band and the
# real `E` key handler must never disagree about the word, same
# single-source-of-truth discipline the retired imports below used to
# keep for their own tokens.
from .autonomy_keys import EXPLORE_TOKEN

# Canon's middle-dot separator for a toggle's ON/OFF suffix
# (`cockpit/strip.py`'s own `SEP` -- both are the same NO-SWAP glyph,
# `visual-language.md` glyph table: `·` never gets an ASCII substitute).
_TOGGLE_SEP = "\u00b7"

# The trainer calm band's own labels (WO-PLAY-STRIP-TRAINER-CHROME).
# Deliberately LOCAL literals, not re-imports of `chains.CHAINS_TOKEN`
# ("L)chains") or the retired `"T)rigger"` -- see the module docstring's
# "What this is now" section for why: this is a calm-band-only RELABEL of
# the same two keys, and every other surface that still cites the popup
# by its own name keeps doing so unchanged.
LOOPS_TOKEN = "L)oops"
TRADE_LOOP_CHAIN_TOKEN = "T)rade Loop Chain"

# The three toggle labels' PREFIX only -- ``compose_teach_band`` appends
# the ``·ON``/``·OFF`` suffix from the caller's own boolean at call time,
# so there is no single fixed "the" token for these three the way there
# is for `LOOPS_TOKEN`/`TRADE_LOOP_CHAIN_TOKEN` above.
PORT_TRADE_LABEL = "P)ort Trade"
CARGO_UPGRADE_LABEL = "C)argo Hold Upgrade"
SHIP_UPGRADE_LABEL = "S)hip Upgrade"


def _toggle_token(label: str, on: object) -> str:
    """``"{label}·ON"`` / ``"{label}·OFF"`` from any caller-supplied
    truthiness. Never raises: an unevaluable ``on`` (a raising
    ``__bool__``) degrades to ``ON`` -- DECISION's own stated default for
    all three trainer toggles, so a hostile/unset value reads as the
    canon-default state rather than an arbitrary OFF.
    """
    try:
        lit = bool(on)
    except Exception:
        lit = True
    return f"{label}{_TOGGLE_SEP}{'ON' if lit else 'OFF'}"


# Canon's standing calm-band spelling (DECISION
# `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 2). A tuple, not a
# flat string, so a later WO can extend it additively. Rendered at the
# DEFAULT (all-ON) toggle state -- `compose_teach_band`'s own toggle
# kwargs recompute the three toggle tokens for any other state; this
# tuple is the reference/default reading other modules may check
# membership against (mirroring the old band's `TEACH_TOKENS` seam).
TEACH_TOKENS: tuple[str, ...] = (
    EXPLORE_TOKEN,
    _toggle_token(PORT_TRADE_LABEL, True),
    LOOPS_TOKEN,
    TRADE_LOOP_CHAIN_TOKEN,
    _toggle_token(CARGO_UPGRADE_LABEL, True),
    _toggle_token(SHIP_UPGRADE_LABEL, True),
)

# Two spaces between tokens -- canon renders the band that way in every
# example it gives (`:136`, `:220`, `visual-language.md §"A calm cockpit reading (App healthy, nothing to see)"`), and it is
# the same gap `arm.ARM_GAP` uses between chips.
TOKEN_GAP = "  "

# The tone NAME (not an attr) the draw layer resolves to canon's cyan
# chrome accent. A distinct name rather than `None`, because `None`
# already means "plain, uncolored" for the liveness cluster and the
# inter-chip separators -- the band must be cyan chrome, and reusing
# `None` would render it uncolored while looking correct in every
# segment-level test.
TEACH_TONE = "chrome"


def compose_teach_band(
    *,
    unicode_ok: object = True,
    port_trade_on: object = True,
    cargo_upgrade_on: object = True,
    ship_upgrade_on: object = True,
) -> str:
    """The standing calm-band hint line as one plain string.

    ``E)xplore  P)ort Trade·{ON|OFF}  L)oops  T)rade Loop Chain
    C)argo Hold Upgrade·{ON|OFF}  S)hip Upgrade·{ON|OFF}`` -- see the
    module docstring for what each token means and why P/C/S carry a
    caller-supplied boolean instead of a fixed word. All three toggle
    kwargs default to ``True`` (DECISION's own stated default), so
    calling this with no arguments reproduces `TEACH_TOKENS` joined
    verbatim.

    ``unicode_ok`` is accepted and ignored (see the module docstring:
    `KEY)verb` has no Unicode twin). Never raises.
    """
    tokens = (
        EXPLORE_TOKEN,
        _toggle_token(PORT_TRADE_LABEL, port_trade_on),
        LOOPS_TOKEN,
        TRADE_LOOP_CHAIN_TOKEN,
        _toggle_token(CARGO_UPGRADE_LABEL, cargo_upgrade_on),
        _toggle_token(SHIP_UPGRADE_LABEL, ship_upgrade_on),
    )
    return TOKEN_GAP.join(tokens)
