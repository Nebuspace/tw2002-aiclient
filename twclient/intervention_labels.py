"""Shared WS5 intervention reason codes → short human labels.

Single source of truth for play (product adapters) and spectate layout.
Display only — protocol codes are unchanged. Lives in ``twclient`` so
ops spectate never imports the product package (no aiclient cycle).
"""

from __future__ import annotations

INTERVENTION_REASON_LABELS = {
    "autopilot_halted": "autopilot halted",
    "autopilot_no_candidates": "autopilot no candidates",
    "autopilot_max_ticks_exhausted": "autopilot max ticks exhausted",
    "autopilot_game_select": "autopilot game select",
    "explore_exhausted": "explore exhausted",
    "human_attach_blocks_trainer": "human attach blocks trainer",
    "credits_unknown": "credits unknown",
    "credits_stale": "credits stale",
    "fighters_unknown": "fighters unknown",
    "fighters_stale": "fighters stale",
}


def intervention_reason_label(code) -> str:
    """Map a reason ``code`` to a short label; unknown codes pass through."""
    if code is None or code == "":
        return "?"
    text = str(code)
    return INTERVENTION_REASON_LABELS.get(text, text)
