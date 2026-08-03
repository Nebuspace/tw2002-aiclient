"""PWO-113 — refuse PvP-aggression rule proposals (alignment gate).

Canon (``canon/doctrine/alignment-and-conduct.md`` M1): no taught rule may
encode initiate-PvP; the teacher/rule pipeline must decline to author such a
rule. Combat/PvP is STOP + escalate for the human — never an App macro.

Ceiling
-------
This module is a **proposal gate** only. Fire-time NPC toll PvP boundary
lives in ``session/fighter_toll_policy`` (``pvp_hard_stop``). Coach prose is
not a gate. This refuse-path does not invent a screen classifier.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = [
    "AlignmentRefusal",
    "refuse_pvp_aggression_rule",
]

# Exact screen_match values that mean player combat / PvP (denylist).
_PVP_SCREEN_EXACT = frozenset(
    {
        "player_attack",
        "pvp_combat",
        "player_combat",
        "pvp_confirm",
        "pvp_option",
    }
)

# Substrings in screen_match (casefold) that mark PvP screens.
_PVP_SCREEN_SUBSTR = ("pvp", "player_attack", "player_combat")

# Exact do / macro names that encode initiate-PvP regardless of screen.
_PVP_DO_EXACT = frozenset(
    {
        "attack-player",
        "attack_player",
        "pvp-attack",
        "pvp_attack",
        "initiate-pvp",
        "initiate_pvp",
        "hunt-player",
    }
)

# Attack keystrokes / macros that are only refused when the *screen* is PvP.
# Bare ``a`` / ``attack`` on a corp-toll screen must remain allowed.
_ATTACK_ON_PVP_SCREEN = frozenset({"a", "y", "attack", "attack-npc"})

# Explicit corp-toll screens — negative control for false positives.
_CORP_TOLL_SCREENS = frozenset(
    {
        "fighter_toll",
        "corp_toll",
        "option_toll",
        "fighter_option",
    }
)


class AlignmentRefusal(ValueError):
    """A rule document was refused because it would encode initiate-PvP."""


def _is_pvp_screen(screen: str) -> bool:
    folded = screen.casefold()
    if folded in _PVP_SCREEN_EXACT:
        return True
    return any(token in folded for token in _PVP_SCREEN_SUBSTR)


def _is_corp_toll_screen(screen: str) -> bool:
    return screen.casefold() in _CORP_TOLL_SCREENS


def refuse_pvp_aggression_rule(document: Mapping[str, Any]) -> None:
    """Raise :class:`AlignmentRefusal` if *document* encodes PvP aggression.

    Allowed documents return ``None``. Callers map the refusal into their
    own error type (``RuleWriteError`` / ``DraftBridgeError``).
    """
    if not isinstance(document, Mapping):
        return
    screen = document.get("screen_match")
    do = document.get("do")
    if not isinstance(screen, str) or not isinstance(do, str):
        return
    screen_f = screen.casefold().strip()
    do_f = do.casefold().strip()
    if not screen_f or not do_f:
        return

    # Corp toll negative control: NPC Attack on a toll frame is not initiate-PvP.
    if _is_corp_toll_screen(screen_f):
        return

    if do_f in _PVP_DO_EXACT:
        raise AlignmentRefusal(
            "alignment refuses a rule that initiates PvP "
            f"(do={do!r}) — no taught rule may encode player aggression"
        )

    if _is_pvp_screen(screen_f):
        if do_f in _ATTACK_ON_PVP_SCREEN or do_f in _PVP_DO_EXACT:
            raise AlignmentRefusal(
                "alignment refuses a rule that initiates PvP "
                f"(screen_match={screen!r}, do={do!r}) — combat is human-gated"
            )
        # Any macro bound to an explicit PvP screen is initiate-PvP content.
        raise AlignmentRefusal(
            "alignment refuses a rule matched to a PvP/player-combat screen "
            f"(screen_match={screen!r}) — teacher must decline, not author"
        )
