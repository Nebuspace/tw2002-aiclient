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

    E)xplore  F)ind StarDock·ON  P)ort Trade·ON  C)argo Hold Upgrade·ON
    S)hip Upgrade·ON  │  T)rade Loop Chain  L)ist Loops

  Two clusters (Explore toggles, then loop tools), separated by a
  NO-SWAP ``│`` token (same spirit as middle-dot ``·``: no ASCII twin).
  Left/right pad of two spaces is baked into ``compose_teach_band`` so
  the band is not flush to the seat chip / liveness cluster.

- `E)xplore` reuses `autonomy_keys.EXPLORE_TOKEN` verbatim -- same key,
  same word, already trainer-plain. Starts/restarts Explore; intent is
  gated by `F)ind StarDock` (below).
- `F)ind StarDock` is an Explore-cluster toggle (default **ON**): when
  ON, `E` / App-armed explore hunt StarDock; when OFF, map-fill instead.
  `F` was previously the unadvertised fight-tolls opt-in; that binding
  moved to `X` so calm chrome can teach Find StarDock on its mnemonic.
- `L)ist Loops` (``LOOPS_TOKEN``) is ``chains.CHAINS_TOKEN`` imported
  under the calm-band name (WO-LOOPS-POPUP-OVERLAY) -- same `L` key,
  same overlay, one spelling for chrome and HELP.
- `T)rade Loop Chain` starts/stops the L-armed Trade Loop
  (`screens.py`'s `trade_loop_toggle` intent; Assign-Trigger is not calm `T`).
  WO-EXPLORE-TRADE-MODE-SPLIT / RESOLVED-EXPLORE-VS-TRADE-LOOP-MODES.
- `P)ort Trade`, `C)argo Hold Upgrade`, `S)hip Upgrade` are toggles
  (WO-PLAY-STRIP-TRAINER-CHROME): each renders `·ON`/`·OFF` from a
  caller-supplied boolean (default **ON**, per DECISION), driven by
  `PlayShellScreen`'s own local Play state. `P`/`C`/`S`
  (`screens.py::PlayShellScreen.handle_key`, REVISE 2026-07-31) flip
  their own boolean directly and return no intent -- the daemon-side
  spend gate for Trade Loop **execution** is `T` when Port Trade is ON
  (FOCUS no longer silent-fires `run_chain`). Cargo upgrade may still
  App-armed auto-fire via `_autonomy_auto_fire`. `ship_upgrade_on` alone
  still gates nothing --
  no ship-upgrade engine or offer kind exists yet, an honest absence
  rather than an unwired follow-on. `P` is DELIBERATELY no longer
  `cockpit.panic`'s key on this calm path (the STATUS-DONE cut of this
  WO left that old wire live underneath the new label, a
  plausible-but-wrong claim caught in hub REVISE): `cockpit/panic.py`
  itself is untouched, only the calm-path binding moved; Mode-leave
  (Ctrl-A to Manual) is the operator's own halt now (DECISION point 1),
  not this retired `P`.

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
from .chains import CHAINS_TOKEN as LOOPS_TOKEN

# Canon's middle-dot separator for a toggle's ON/OFF suffix
# (`cockpit/strip.py`'s own `SEP` -- both are the same NO-SWAP glyph,
# `visual-language.md` glyph table: `·` never gets an ASCII substitute).
_TOGGLE_SEP = "\u00b7"

# The trainer calm band's own labels (WO-PLAY-STRIP-TRAINER-CHROME /
# WO-LOOPS-POPUP-OVERLAY / WO-FIND-STARDOCK-TOGGLE). ``LOOPS_TOKEN`` is
# ``chains.CHAINS_TOKEN`` (single source). ``T)rade Loop Chain`` stays a
# local relabel of the retired `"T)rigger"` wire -- see the module docstring.
TRADE_LOOP_CHAIN_TOKEN = "T)rade Loop Chain"

# Toggle labels' PREFIX only -- ``compose_teach_band`` appends the
# ``·ON``/``·OFF`` suffix from the caller's own boolean at call time.
FIND_STARDOCK_LABEL = "F)ind StarDock"
PORT_TRADE_LABEL = "P)ort Trade"
CARGO_UPGRADE_LABEL = "C)argo Hold Upgrade"
SHIP_UPGRADE_LABEL = "S)hip Upgrade"


def _toggle_token(label: str, on: object) -> str:
    """``"{label}·ON"`` / ``"{label}·OFF"`` from any caller-supplied
    truthiness. Never raises: an unevaluable ``on`` (a raising
    ``__bool__``) degrades to ``ON`` -- DECISION's own stated default for
    trainer toggles, so a hostile/unset value reads as the
    canon-default state rather than an arbitrary OFF.
    """
    try:
        lit = bool(on)
    except Exception:
        lit = True
    return f"{label}{_TOGGLE_SEP}{'ON' if lit else 'OFF'}"


# Canon's standing calm-band spelling (DECISION
# `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 2 + Find StarDock).
# A tuple, not a flat string, so a later WO can extend it additively.
# Rendered at the DEFAULT (all-ON) toggle state -- `compose_teach_band`'s
# own toggle kwargs recompute tokens for any other state; this tuple is
# the reference/default reading other modules may check membership against.
# Cluster separator between the Explore toggle cluster (E+F+P+C+S) and the
# loop-tools cluster (T+L). Own TEACH_TOKENS element so membership checks
# work; NO-SWAP like middle-dot ``·`` (no ASCII twin on ``unicode_ok=False``).
CLUSTER_SEP = "│"  # │

TEACH_TOKENS: tuple[str, ...] = (
    EXPLORE_TOKEN,
    _toggle_token(FIND_STARDOCK_LABEL, True),
    _toggle_token(PORT_TRADE_LABEL, True),
    _toggle_token(CARGO_UPGRADE_LABEL, True),
    _toggle_token(SHIP_UPGRADE_LABEL, True),
    CLUSTER_SEP,
    TRADE_LOOP_CHAIN_TOKEN,
    LOOPS_TOKEN,
)

# Two spaces between tokens -- canon renders the band that way in every
# example it gives (`:136`, `:220`, `visual-language.md §"A calm cockpit reading (App healthy, nothing to see)"`), and it is
# the same gap `arm.ARM_GAP` uses between chips.
TOKEN_GAP = "  "

# Left/right pad baked into ``compose_teach_band`` only (not into
# ``TEACH_TOKENS``) so the calm band is not flush to seat chip / liveness.
BAND_PAD = "  "

# The tone NAME (not an attr) the draw layer resolves to canon's cyan
# chrome accent. A distinct name rather than `None`, because `None`
# already means "plain, uncolored" for the liveness cluster and the
# inter-chip separators -- the band must be cyan chrome, and reusing
# `None` would render it uncolored while looking correct in every
# segment-level test.
TEACH_TONE = "chrome"


# Short toggle prefixes under width pressure (WO-STRIP-HOTFIX-FIT-TRADE-LOGS).
# Wide-terminal default still uses the long labels above.
FIND_STARDOCK_LABEL_SHORT = "F)ind"
PORT_TRADE_LABEL_SHORT = "P)ort"
CARGO_UPGRADE_LABEL_SHORT = "C)argo"
SHIP_UPGRADE_LABEL_SHORT = "S)hip"


def _join_band(tokens: tuple[str, ...], *, gap: str, pad: str) -> str:
    return f"{pad}{gap.join(tokens)}{pad}"


def fit_teach_band(
    budget: object,
    *,
    unicode_ok: object = True,
    find_stardock_on: object = True,
    port_trade_on: object = True,
    cargo_upgrade_on: object = True,
    ship_upgrade_on: object = True,
) -> str:
    """Return the widest calm teach band that fits ``budget`` columns.

    Ladder (wide → narrow), stop at first that fits
    (WO-STRIP-HOTFIX-FIT-TRADE-LOGS / WO-FIND-STARDOCK-TOGGLE):

    1. Full labels + ``BAND_PAD`` (same as unlimited ``compose_teach_band``)
    2. Short toggles ``F)ind·ON`` / ``P)ort·ON`` / ``C)argo·ON`` / ``S)hip·ON``
    3. Reduce ``BAND_PAD`` / token-gap padding
    4. Drop S, then C, then F (keep E P T L)
    5. Drop ``│`` if needed
    6. Last resort empty only if even ``E)xplore  L)ist Loops`` will not fit

    ``unicode_ok`` accepted and ignored. Never raises. Returns ``""`` when
    ``budget`` is not a usable positive int or nothing fits.
    """
    del unicode_ok  # API uniformity with compose_teach_band
    try:
        room = int(budget)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""
    if room <= 0:
        return ""

    find_long = _toggle_token(FIND_STARDOCK_LABEL, find_stardock_on)
    port_long = _toggle_token(PORT_TRADE_LABEL, port_trade_on)
    cargo_long = _toggle_token(CARGO_UPGRADE_LABEL, cargo_upgrade_on)
    ship_long = _toggle_token(SHIP_UPGRADE_LABEL, ship_upgrade_on)
    find_s = _toggle_token(FIND_STARDOCK_LABEL_SHORT, find_stardock_on)
    port_s = _toggle_token(PORT_TRADE_LABEL_SHORT, port_trade_on)
    cargo_s = _toggle_token(CARGO_UPGRADE_LABEL_SHORT, cargo_upgrade_on)
    ship_s = _toggle_token(SHIP_UPGRADE_LABEL_SHORT, ship_upgrade_on)

    candidates: list[str] = [
        # 1 — full calm default
        _join_band(
            (
                EXPLORE_TOKEN,
                find_long,
                port_long,
                cargo_long,
                ship_long,
                CLUSTER_SEP,
                TRADE_LOOP_CHAIN_TOKEN,
                LOOPS_TOKEN,
            ),
            gap=TOKEN_GAP,
            pad=BAND_PAD,
        ),
        # 2 — short toggle labels
        _join_band(
            (
                EXPLORE_TOKEN,
                find_s,
                port_s,
                cargo_s,
                ship_s,
                CLUSTER_SEP,
                TRADE_LOOP_CHAIN_TOKEN,
                LOOPS_TOKEN,
            ),
            gap=TOKEN_GAP,
            pad=BAND_PAD,
        ),
        # 3 — tighter pad / gap
        _join_band(
            (
                EXPLORE_TOKEN,
                find_s,
                port_s,
                cargo_s,
                ship_s,
                CLUSTER_SEP,
                TRADE_LOOP_CHAIN_TOKEN,
                LOOPS_TOKEN,
            ),
            gap=TOKEN_GAP,
            pad=" ",
        ),
        _join_band(
            (
                EXPLORE_TOKEN,
                find_s,
                port_s,
                cargo_s,
                ship_s,
                CLUSTER_SEP,
                TRADE_LOOP_CHAIN_TOKEN,
                LOOPS_TOKEN,
            ),
            gap=" ",
            pad=" ",
        ),
        _join_band(
            (
                EXPLORE_TOKEN,
                find_s,
                port_s,
                cargo_s,
                ship_s,
                CLUSTER_SEP,
                TRADE_LOOP_CHAIN_TOKEN,
                LOOPS_TOKEN,
            ),
            gap=" ",
            pad="",
        ),
        # 4 — drop S, then C, then F
        _join_band(
            (
                EXPLORE_TOKEN,
                find_s,
                port_s,
                cargo_s,
                CLUSTER_SEP,
                TRADE_LOOP_CHAIN_TOKEN,
                LOOPS_TOKEN,
            ),
            gap=" ",
            pad=" ",
        ),
        _join_band(
            (
                EXPLORE_TOKEN,
                find_s,
                port_s,
                CLUSTER_SEP,
                TRADE_LOOP_CHAIN_TOKEN,
                LOOPS_TOKEN,
            ),
            gap=" ",
            pad=" ",
        ),
        _join_band(
            (
                EXPLORE_TOKEN,
                port_s,
                CLUSTER_SEP,
                TRADE_LOOP_CHAIN_TOKEN,
                LOOPS_TOKEN,
            ),
            gap=" ",
            pad=" ",
        ),
        # 5 — drop cluster sep
        _join_band(
            (EXPLORE_TOKEN, port_s, TRADE_LOOP_CHAIN_TOKEN, LOOPS_TOKEN),
            gap=" ",
            pad=" ",
        ),
        _join_band(
            (EXPLORE_TOKEN, port_s, TRADE_LOOP_CHAIN_TOKEN, LOOPS_TOKEN),
            gap=" ",
            pad="",
        ),
        # last honest minimum before empty
        _join_band((EXPLORE_TOKEN, LOOPS_TOKEN), gap=TOKEN_GAP, pad=" "),
        _join_band((EXPLORE_TOKEN, LOOPS_TOKEN), gap=" ", pad=""),
    ]
    for cand in candidates:
        if len(cand) <= room:
            return cand
    return ""


def compose_teach_band(
    *,
    unicode_ok: object = True,
    find_stardock_on: object = True,
    port_trade_on: object = True,
    cargo_upgrade_on: object = True,
    ship_upgrade_on: object = True,
    width: object = None,
) -> str:
    """The standing calm-band hint line as one plain string.

    ``  E)xplore  F)ind StarDock·{ON|OFF}  P)ort Trade·{ON|OFF}
    C)argo Hold Upgrade·{ON|OFF}  S)hip Upgrade·{ON|OFF}  │
    T)rade Loop Chain  L)ist Loops  `` -- Explore cluster, ``│``
    separator, loop-tools cluster; left/right ``BAND_PAD``.

    All toggle kwargs default to ``True`` (DECISION defaults + Find
    StarDock ON so `E` keeps today's hunt behavior).

    ``width`` (WO-STRIP-HOTFIX-FIT-TRADE-LOGS): when a positive int, return
    ``fit_teach_band(width, ...)`` so callers can request a budgeted band.
    ``None`` / non-int / non-positive keeps the unlimited full-label default.

    ``unicode_ok`` is accepted and ignored (see the module docstring:
    `KEY)verb` and cluster ``│`` have no Unicode twin / are NO-SWAP).
    Never raises.
    """
    if width is not None:
        try:
            w = int(width)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            w = 0
        if w > 0:
            return fit_teach_band(
                w,
                unicode_ok=unicode_ok,
                find_stardock_on=find_stardock_on,
                port_trade_on=port_trade_on,
                cargo_upgrade_on=cargo_upgrade_on,
                ship_upgrade_on=ship_upgrade_on,
            )

    tokens = (
        EXPLORE_TOKEN,
        _toggle_token(FIND_STARDOCK_LABEL, find_stardock_on),
        _toggle_token(PORT_TRADE_LABEL, port_trade_on),
        _toggle_token(CARGO_UPGRADE_LABEL, cargo_upgrade_on),
        _toggle_token(SHIP_UPGRADE_LABEL, ship_upgrade_on),
        CLUSTER_SEP,
        TRADE_LOOP_CHAIN_TOKEN,
        LOOPS_TOKEN,
    )
    return f"{BAND_PAD}{TOKEN_GAP.join(tokens)}{BAND_PAD}"
