"""Early-game autonomy key labels for the calm teach band
(WO-PLAY-HELP-AUTONOMY-KEYS).

Copy only. The Play key handlers already live in ``app.py`` (`E` explore,
`H` hold-buy, `O` FOCUS offer, `L` chains). This module names those
affordances so the standing chrome cannot drift off the wires — same
``TOKEN`` import pattern as ``reflex_controls.REFLEX_TOKEN`` /
``chains.CHAINS_TOKEN``.

Confirm-not-auto is still load-bearing for what PRESSING ``H``/``O``
themselves do: both only ever raise the existing confirm gate; neither
key press auto-arms anything, and the ``?`` on those tokens still says so
truthfully. What is NO LONGER true (WO-PLAY-STRIP-POLICY-AUTO, DECISION
`RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 6) is that this was the
calm path's own standing doctrine: under APP-ARMED with the matching
toggle ON, the App now reaches the identical hold-buy/trade-loop outcome
through `app.py`'s own idle-tick auto-fire, with no key press and no
confirm at all. ``H``/``O`` remain honest manual fallbacks -- useful in
Manual mode, or when the toggle is OFF -- not a claim that nothing on this
surface ever auto-acts. See ``HOLD_HELP``/``OFFER_HELP`` below for the
operator-facing wording.
"""

from __future__ import annotations

from .chains import CHAINS_TOKEN

EXPLORE_TOKEN = "E)xplore"
HOLD_TOKEN = "H)old?"
OFFER_TOKEN = "O)ffer?"

# Honest one-liners — pins + any future help overlay. Not joined into the
# standing band (width budget); teachband ships the short TOKEN forms.
EXPLORE_HELP = "E)xplore — start explore via confirm gate"
# WO-PLAY-STRIP-POLICY-AUTO: no longer "(not auto)" unconditionally -- see
# this module's own docstring for why. Both lines state what the KEY press
# itself still does (manual confirm) alongside the real App-armed auto path
# that now exists beside it, rather than the old blanket "not auto" claim.
# Kept under the same ~60-char budget the old "(not auto)" lines held
# (`tests/test_cockpit_fold.py`'s width=60 fold-composer pins truncate any
# HELP line longer than that, same clip contract every composer here
# documents) -- "under APP-ARMED + ON" is the compact form; the P/C/S
# toggle names themselves are spelled out on the calm band the operator is
# already looking at (`teachband.py`), not repeated here.
HOLD_HELP = "H)old? — manual confirm; APP-ARMED + ON auto-buys"
OFFER_HELP = "O)ffer? — manual confirm; APP-ARMED + ON auto-acts"
CHAINS_HELP = "L)ist Loops — pick; T)rade Loop Chain runs"


def compose_autonomy_help_lines() -> tuple[str, ...]:
    """Ordered early-game key one-liners (E · H · O · L). Never raises."""
    return (EXPLORE_HELP, HOLD_HELP, OFFER_HELP, CHAINS_HELP)


# Re-export so callers that import this module for the early-game cluster
# see L beside O/H without a second import.
__all__ = (
    "CHAINS_HELP",
    "CHAINS_TOKEN",
    "EXPLORE_HELP",
    "EXPLORE_TOKEN",
    "HOLD_HELP",
    "HOLD_TOKEN",
    "OFFER_HELP",
    "OFFER_TOKEN",
    "compose_autonomy_help_lines",
)
