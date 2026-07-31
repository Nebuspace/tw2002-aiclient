"""Early-game autonomy key labels for the calm teach band
(WO-PLAY-HELP-AUTONOMY-KEYS).

Copy only. The Play key handlers already live in ``app.py`` (`E` explore,
`H` hold-buy, `O` FOCUS offer, `L` chains). This module names those
affordances so the standing chrome cannot drift off the wires — same
``TOKEN`` import pattern as ``reflex_controls.REFLEX_TOKEN`` /
``chains.CHAINS_TOKEN``.

Confirm-not-auto is load-bearing for ``H`` and ``O``: both only raise the
existing confirm gate; neither auto-arms. The ``?`` on those tokens and
the HELP one-liners spell that out for the operator (Ada would otherwise
miss ``O`` entirely).
"""

from __future__ import annotations

from .chains import CHAINS_TOKEN

EXPLORE_TOKEN = "E)xplore"
HOLD_TOKEN = "H)old?"
OFFER_TOKEN = "O)ffer?"

# Honest one-liners — pins + any future help overlay. Not joined into the
# standing band (width budget); teachband ships the short TOKEN forms.
EXPLORE_HELP = "E)xplore — start explore via confirm gate"
HOLD_HELP = "H)old? — hold buy confirm when scaffold complete (not auto)"
OFFER_HELP = "O)ffer? — top FOCUS candidate → confirm (not auto)"
CHAINS_HELP = "L)chains — taught trade-loop chains library"


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
