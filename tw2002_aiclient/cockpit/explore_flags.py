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

# What the confirm line gains when a flag is ON. Absent when OFF -- the
# default line must stay byte-identical to the pre-WO prompt, so existing
# muscle memory and the pins that assert `("Explore", 5)` both still hold.
DOCK_MARKER = "+dock"
TOLLS_MARKER = "+fight-tolls"

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
    """Add the ON markers to the confirm line's action text.

    With both flags OFF this returns *action* unchanged, so the default
    prompt is byte-identical to the pre-WO one. With a flag ON the marker
    is appended, because the gate must describe the run it actually arms.

    Truthiness is used for the *display* decision only -- a caller that
    somehow held a non-bool still gets a marker rather than a silently
    plain line, which is the fail-loud direction for a prompt. The value
    handed to the adapter is never derived from this function.
    """
    text = action if isinstance(action, str) else ""
    parts = [text] if text else []
    if dock:
        parts.append(DOCK_MARKER)
    if tolls:
        parts.append(TOLLS_MARKER)
    return " ".join(parts)


def describe_dock(enabled: object) -> str:
    """Status-line text for the dock toggle's new state. Never raises."""
    return _DOCK_ON if enabled else _DOCK_OFF


def describe_tolls(enabled: object) -> str:
    """Status-line text for the fight-tolls toggle's new state. Never raises."""
    return _TOLLS_ON if enabled else _TOLLS_OFF
