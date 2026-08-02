"""Early-game autonomy key labels for the calm teach band
(WO-PLAY-HELP-AUTONOMY-KEYS; vocab refresh WO-AUTONOMY-HELP-VOCAB).

Copy only. Play key handlers live in ``app.py`` / ``screens.py``. This
module names the **calm teachband** affordances so DECISIONS empty-state
help cannot drift off the strip (same ``TOKEN`` import pattern as
``reflex_controls.REFLEX_TOKEN`` / ``chains.CHAINS_TOKEN``).

Calm vocabulary (DECISION ``RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731``
plus Find StarDock explore toggle):
``E)xplore`` · ``F)ind StarDock·ON/OFF`` · ``P/C/S`` App-armed policy
toggles · ``T)rade Loop Chain`` · ``L)ist Loops`` · Mode/^A App↔Manual
(= halt). Hold?/Offer? remain wired keys underneath but are **not** taught
on this help surface (retired from the calm band). App-armed + ·ON is the
default automation path — no confirm-gate doctrine here.
"""

from __future__ import annotations

from .chains import CHAINS_TOKEN

EXPLORE_TOKEN = "E)xplore"
HOLD_TOKEN = "H)old?"
OFFER_TOKEN = "O)ffer?"

# Honest one-liners — pins + DECISIONS calm-empty. Not joined into the
# standing band (width budget); teachband ships the short TOKEN forms.
# ~60-char budget: ``tests/test_cockpit_fold.py`` width=60 clips longer lines.
EXPLORE_HELP = "E)xplore — App-armed run; F)ind StarDock·ON hunts"
POLICY_HELP = "P)ort Trade · C/S — App-armed policy toggles"
MODE_HELP = "Mode/^A — leave App to Manual (= halt)"
CHAINS_HELP = "L)ist Loops — pick; T)rade Loop Chain runs"


def compose_autonomy_help_lines() -> tuple[str, ...]:
    """Ordered calm-band key one-liners (E/F · P/C/S · Mode · L/T). Never raises."""
    return (EXPLORE_HELP, POLICY_HELP, MODE_HELP, CHAINS_HELP)


# Re-export so callers that import this module for the early-game cluster
# see L beside E without a second import.
__all__ = (
    "CHAINS_HELP",
    "CHAINS_TOKEN",
    "EXPLORE_HELP",
    "EXPLORE_TOKEN",
    "HOLD_TOKEN",
    "MODE_HELP",
    "OFFER_TOKEN",
    "POLICY_HELP",
    "compose_autonomy_help_lines",
)
