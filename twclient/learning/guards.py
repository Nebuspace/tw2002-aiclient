"""Pure paladin-ethos + combat-authority guards for the learning loop.

These never send keys. They only classify / block candidate actions so
the dry-run loop cannot even *propose* griefing or unconfirmed combat
as its top pick without an explicit human-confirm flag in context.
"""

# Actions that imply player-combat intent (reversible-full-auto excluded;
# irreversible-first-fire-confirmed boundary lives at the exec-flip, not here).
_COMBAT_ACTION_MARKERS = frozenset({"a", "A", "attack", "ATTACK", "fight", "FIGHT"})


def is_combat_action(action: str) -> bool:
    """True when ``action`` is classified as player-combat intent."""
    if not action:
        return False
    return action in _COMBAT_ACTION_MARKERS or action.lower() in {"attack", "fight"}


def blocked_actions_for_context(
    *,
    authority: str = "ai",
    human_combat_confirmed: bool = False,
) -> frozenset[str]:
    """Return actions the candidate generator must exclude.

    Combat authority is App→AI within paladin bounds: the AI lane never
    proposes combat unless ``human_combat_confirmed`` is True. The App
    (trainer) lane may surface combat candidates for coaching, but still
    treats unconfirmed combat as blocked for autonomous try-then-verify.
    """
    if human_combat_confirmed:
        return frozenset()
    # Both authorities: block combat markers until human confirms.
    # ``authority`` is retained for callers / future App-vs-AI nuance.
    _ = authority
    return frozenset(_COMBAT_ACTION_MARKERS)
