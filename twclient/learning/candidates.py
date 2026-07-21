"""Ranked action candidates for an unknown / stuck state signature.

Pure: no I/O, no daemon. Never invents keystrokes — only ranks from the
caller-supplied ``known_actions`` set.
"""


def propose_candidates(
    state_signature: str,
    *,
    known_actions: list[str] | None = None,
    prior_rules: list[dict] | None = None,
    blocked_actions: set[str] | frozenset[str] | None = None,
) -> list[dict]:
    """Propose ranked try-actions for ``state_signature``.

    Each item: ``{"action": str, "score": float, "reason": str}``,
    highest score first. Returns ``[]`` when ``known_actions`` is empty
    or None (never invents keys).
    """
    if not state_signature or not str(state_signature).strip():
        return []
    actions = list(known_actions or [])
    if not actions:
        return []
    blocked = frozenset(blocked_actions or ())
    tried = {
        str(r.get("tried_action"))
        for r in (prior_rules or [])
        if r.get("tried_action")
    }
    conf_by_action = {
        str(r["tried_action"]): float(r.get("confidence") or 0.0)
        for r in (prior_rules or [])
        if r.get("tried_action")
    }

    ranked: list[dict] = []
    for action in actions:
        if action in blocked:
            continue
        if action in tried:
            # Already observed — demote; still useful for re-verify.
            score = 0.3 + 0.4 * conf_by_action.get(action, 0.0)
            reason = "revisit prior rule"
        else:
            score = 1.0
            reason = "unexplored"
        ranked.append({"action": action, "score": score, "reason": reason})

    ranked.sort(key=lambda c: (-c["score"], c["action"]))
    return ranked
