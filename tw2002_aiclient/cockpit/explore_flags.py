"""Play's explicit, default-OFF opt-in for the two explore automation flags
(WO-PLAY-EXPLORE-FLAGS).

# What this is for

`adapters.explore_start_for_profile` has accepted `dock_new_ports` and
`fight_tolls` since WO-EXPLORE-DOCK-NEW-PORT / WO-FIGHTER-TOLL-POLICY-WIRE,
and the daemon reads both (`session/protocol.py`). Play passed **neither** --
the call site carried a placeholder comment saying "Opt-in later via an
explicit Play control if added". This module is that control.

# Why the opt-in is a separate keystroke, not part of `y`

WO-EXPLORE-DOCK-DEFAULT-OFF made dock default OFF *until the dialect was
known*; the dialect is now known (WO-EXPLORE-DOCK-DIALECT, #211) but the
default stays OFF because these two flags change what a run **spends**.
`y` at the confirm gate must keep meaning exactly what the line above it
says, so the opt-in happens BEFORE the gate is raised and is then spelled
out IN the line the operator confirms. An opt-in that rode along silently on
`y` would make the confirm gate describe a run other than the one it starts,
which is the one thing that gate exists to prevent.

# The two flags are NOT symmetrical, and must not be tidied into symmetry

`adapters.py` deliberately treats them differently:

    :206   payload["dock_new_ports"] = bool(dock_new_ports)
    :225   payload["fight_tolls"] = fight_tolls        # NOT bool(...)

`fight_tolls` is forwarded **un-coerced** so a non-bool such as ``"no"``
reaches the daemon and trips `invalid_fight_tolls`. Coerced, ``bool("no")``
is ``True`` -- an operator who declined combat would have armed it. That
asymmetry was hub-Accept'd as a correct deviation (2026-07-29T03:13Z).

This module therefore holds its state as real ``bool`` objects and hands
them over untouched. It never calls ``bool()`` on either flag: here that
would be a no-op *today* (a toggle can only produce ``True``/``False``), and
that is precisely why it is dangerous to write -- it reads as harmless
tidying, matches `session/cli.py:952`'s house style, and survives review, so
it would still be there the day a non-bool can reach this layer.
`tests/test_play_explore_flags.py` pins the absence structurally.

# Hardening family

Matches `armconfirm.py` / `arm.py` / `teachband.py`: never raises, whatever
it is handed. Key resolution is enumerate-the-open-set (an unknown key is
simply not a toggle); the *safe* outcome here is "no state change", which is
what every unrecognised input gets.
"""

from __future__ import annotations

# The toggle keys. Verified unbound elsewhere in this app at time of
# writing: `E` raises the explore gate, `G` relaunch, `L` chains, `P` panic,
# Space pause, `y`/`Y` confirm, and teach `A`/`R`/`T` stay reserved for
# WO-067/068/069. `D` for dock and `F` for fight are the mnemonic pair.
DOCK_TOGGLE_KEYS = frozenset({ord("d"), ord("D")})
TOLLS_TOGGLE_KEYS = frozenset({ord("f"), ord("F")})

# What the confirm line gains for each flag.
#
# **The dock marker is emitted in BOTH directions; the tolls marker only when
# ON. That asymmetry is the point of WO-EXPLORE-GATHER-VISIBLE.**
#
# This block used to say "absent when OFF -- the default line must stay
# byte-identical to the pre-WO prompt, so existing muscle memory and the pins
# that assert `("Explore", 5)` both still hold." That was a real argument and
# it was wrong in the way that only live use reveals: it made the OFF state
# *invisible by construction*. An operator who never guessed `D` existed saw
# `Explore x5 LIVE?  y/N`, said yes, and warped past every port wondering why
# nothing was investigated (Max, live 2026-07-29). Muscle memory was
# preserved by hiding the one fact the prompt most needed to state.
#
# The invariant this module already claimed two comments down -- "the gate
# must describe the run it arms" -- was only ever applied to the ON
# direction. A run that PASSES PORTS BY is just as much a property of the run
# as one that docks, so the gate now volunteers both.
#
# `TOLLS_MARKER` deliberately keeps the old asymmetric behaviour and is
# absent when OFF. Naming the affordance is a NUDGE, and nudges are
# directional: pointing an operator at commodity gathering costs them
# nothing, while an equally helpful "F to fight tolls" on every prompt would
# be this module quietly advertising a path that SPENDS fighters. Loud toward
# the safe action, quiet toward the spend.
DOCK_MARKER = "+dock"
# Names the state AND the key, because a prompt that only said "no-dock"
# would fix the invisibility of the state while leaving the affordance just
# as unguessable -- the operator would learn they are missing something and
# still not know what to press.
DOCK_OFF_MARKER = "no-dock (D to gather)"
TOLLS_MARKER = "+fight-tolls"

# Appended to the post-ensure offer status line, which is where an operator
# FIRST learns explore exists. It advertised only `E`; `D` was reachable but
# unadvertised on every surface, which is the "secret D" half of the same
# defect. Kept short on purpose: the offer line is a fixed-length string
# (`_EXPLORE_OFFER_CLASSIFICATION` is the constant `"main_command"`), and
# with this suffix it measures 79 columns -- inside an 80-column terminal by
# one character. A hint that clips is not a hint, and it is the TAIL that
# clips, which is exactly where a new suffix lands.
GATHER_HINT = "D to gather"

# Status-line wording for the toggle itself. States the consequence, not the
# variable name: "dock ON" tells an operator nothing about what it spends.
_DOCK_ON = "dock ON — new ports will be docked for commodities"
_DOCK_OFF = "dock off — ports are passed by"
_TOLLS_ON = "fight-tolls ON — toll demands will be FOUGHT"
_TOLLS_OFF = "fight-tolls off — toll screens halt for you"


def resolve_dock_toggle_key(key: object) -> bool:
    """True iff *key* is the dock opt-in toggle. Never raises.

    ``bool`` is rejected before ``int`` because ``True == ord('\\x01')`` in
    Python and a stray boolean must not read as a keystroke -- the same
    guard `armconfirm.resolve_arm_confirm_key` documents.
    """
    if isinstance(key, bool) or not isinstance(key, int):
        return False
    return key in DOCK_TOGGLE_KEYS


def resolve_tolls_toggle_key(key: object) -> bool:
    """True iff *key* is the fight-tolls opt-in toggle. Never raises."""
    if isinstance(key, bool) or not isinstance(key, int):
        return False
    return key in TOLLS_TOGGLE_KEYS


def compose_explore_action(
    action: object,
    *,
    dock: object = False,
    tolls: object = False,
) -> str:
    """Spell the run's flags into the confirm line's action text.

    The gate must describe the run it actually arms, so **dock is always
    stated** -- `+dock` when the operator opted in, `no-dock (D to gather)`
    when they did not. Silence is not a description: an unmarked line was
    read for a whole live session as "explore", when what it armed was
    "explore, passing every port".

    `tolls` keeps the ON-only behaviour. See `TOLLS_MARKER` for why the two
    are deliberately not symmetric.

    Truthiness is used for the *display* decision only -- a caller that
    somehow held a non-bool still gets a marker rather than a silently
    plain line, which is the fail-loud direction for a prompt. The value
    handed to the adapter is never derived from this function.
    """
    text = action if isinstance(action, str) else ""
    parts = [text] if text else []
    parts.append(DOCK_MARKER if dock else DOCK_OFF_MARKER)
    if tolls:
        parts.append(TOLLS_MARKER)
    return " ".join(parts)


def compose_explore_offer(classification: object, *, cycles: object = None) -> str:
    """The post-ensure status line announcing that explore is available.

    Lives here rather than as an f-string in `app._run_play` for one
    practical reason: this is the operator's FIRST contact with the feature,
    and inside that loop it is unreachable by a unit test. A surface that
    decides whether a capability is discoverable should be assertable
    without a curses harness.

    Purely additive against the pre-WO line -- the `press E` token is kept
    byte-for-byte, because several pins assert on it and, more importantly,
    because the existing affordance was never the broken one. `D` is what
    was missing. Never raises.
    """
    label = classification if isinstance(classification, str) else "?"
    count = cycles if isinstance(cycles, int) and not isinstance(cycles, bool) else None
    run = f"explore ×{count} available" if count is not None else "explore available"
    return f"session ready — {label}  ·  {run} — press E  ·  {GATHER_HINT}"


def describe_dock(enabled: object) -> str:
    """Status-line text for the dock toggle's new state. Never raises."""
    return _DOCK_ON if enabled else _DOCK_OFF


def describe_tolls(enabled: object) -> str:
    """Status-line text for the fight-tolls toggle's new state. Never raises."""
    return _TOLLS_ON if enabled else _TOLLS_OFF
