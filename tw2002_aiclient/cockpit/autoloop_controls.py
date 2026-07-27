"""Cockpit pause + relaunch key resolution and the relaunch confirm label
(WO-AUTOLOOP-RELAUNCH-COCKPIT).

# Pause -- ungated, like panic

Pausing STOPS further sends; it never spends any, so `panic.py`'s own
"the confirm gate protects the direction that spends" argument applies
here unchanged -- see that module's docstring for the full reasoning,
not repeated here. `resolve_pause_key` mirrors `panic.resolve_panic_key`'s
hardening shape exactly (reject non-`int`, reject `bool`, never raise).

# Relaunch -- confirm-gated, and the label must say why

`adapters.autoloop_relaunch` is a money path: it replays a macro from step
1 and re-issues sends the paused run already made. `resolve_relaunch_
offer_key` only says WHICH key *offers* the gate -- the gate mechanics
(`y`/`Y` only, default-deny) stay `cockpit.armconfirm`'s job, reused
verbatim; `app.py::_run_play` calls `PlayShellScreen.begin_arm_confirm`
with this module's composed action text, the same seam the existing
explore offer already uses.

`compose_relaunch_confirm_action` renders the money-path *meaning*, not
raw field names. `replays_from_start` is not one of its parameters:
`adapters.autoloop_relaunch`'s own docstring calls it "always true
today", so the composer states it as fixed prose -- the day the daemon
can relaunch any other way, this composer (and its test) should go red
first, not silently keep printing the old sentence for a new fact.
`sends_already_issued` renders as a plain int for a genuine non-negative
int input, or `"?"` for every other shape -- `None` included, which is
"unknown", the same honest-`?` rule `adapters.py` and `covermeter.py`
already state for their own fields of this kind.

No key bound here is ever named, or resolves to, `"resume"` /
`autoloop_resume` -- that word stays refused (hub ruling 2026-07-27,
options 1+3); see `session/protocol.py::_dispatch_autoloop_relaunch`.

Hardening family (matches `panic.py`/`armconfirm.py`): every public
function is never-raises regardless of input shape.
"""

from __future__ import annotations

# Space -- the halt-direction sibling of `p`/`P` panic. No canon citation
# pins this key yet (the reborn standing hint band names no pause/relaunch
# token today); flagged for hub/Samantha review, same as every other
# affordance this WO adds without a canon-cited key.
_PAUSE_KEYS = frozenset({ord(" ")})

# The intent `screens.py::handle_key` returns for the pause key. Distinct
# from `panic.PANIC_INTENT` so the app loop can never confuse the two even
# though both are ungated.
PAUSE_INTENT = "pause"


def resolve_pause_key(key: object) -> bool:
    """``True`` when ``key`` is the pause hotkey (Space). ``bool`` is
    rejected even though ``isinstance(True, int)`` holds -- the same
    ``panic.resolve_panic_key`` guard against ``True == 1`` matching a
    keycode by accident. Never raises."""
    if isinstance(key, bool) or not isinstance(key, int):
        return False
    return key in _PAUSE_KEYS


# The key that OFFERS the relaunch confirm gate -- checked in the play
# loop (`app.py::_run_play`), not in `screens.py::handle_key`, the same
# split `_EXPLORE_OFFER_KEYS` already uses: the gate lives on
# `PlayShellScreen`, but WHEN to raise it is a play-loop decision the
# screen itself has no state to make.
#
# `G` -- not `L` (canon reserves `L)chains` for the unbuilt Trade-Loop-
# Chains popup, `teachband.py`'s own docstring), and not any already-bound
# letter (`a/A` analyze, `r/R` record, `t/T` trigger, `p/P` panic, `q/Q`
# quit, `e/E` explore). No canon citation pins this letter either.
_RELAUNCH_OFFER_KEYS = frozenset({ord("g"), ord("G")})

# What the confirm line says is about to run, before the disclosure clause.
# Never the word "resume" -- see the module docstring.
RELAUNCH_ACTION_LABEL = "Relaunch"


def resolve_relaunch_offer_key(key: object) -> bool:
    """``True`` when ``key`` offers the relaunch confirm gate. Same
    hardening shape as ``resolve_pause_key``. Never raises."""
    if isinstance(key, bool) or not isinstance(key, int):
        return False
    return key in _RELAUNCH_OFFER_KEYS


def compose_relaunch_confirm_action(sends_already_issued: object) -> str:
    """The relaunch confirm line's meaning clause -- handed to
    ``armconfirm.compose_arm_confirm_line`` as its ``action`` text, which
    appends canon's `` LIVE?  y/N`` suffix.

    Renders ``"Relaunch — replays from the beginning, {n} sends already
    issued"``, where ``{n}`` is a plain int for a genuine non-negative
    ``int`` input, or ``"?"`` for anything else (``None``, a negative int,
    a ``bool``, or any other type) -- unknown is not zero. Never raises
    regardless of input type."""
    if (
        not isinstance(sends_already_issued, bool)
        and isinstance(sends_already_issued, int)
        and sends_already_issued >= 0
    ):
        n = str(sends_already_issued)
    else:
        n = "?"
    return (
        f"{RELAUNCH_ACTION_LABEL} \u2014 replays from the beginning, "
        f"{n} sends already issued"
    )
