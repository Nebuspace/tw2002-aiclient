"""Try→observe→verify→update orchestration — DRY-RUN ONLY.

Structurally cannot execute: this module never imports the daemon,
never calls ``emit_key_if_safe``, and never sends keys. It consumes
state snapshots (or precomputed signatures) and emits a plan/trace
object only.

State keys reuse ``menu_sig.menu_signature`` when raw screen text is
supplied — the hash is never re-derived ad hoc here.
"""

from __future__ import annotations

from ..menu_sig import menu_signature
from .candidates import propose_candidates
from .comparator import compare_transition
from .guards import blocked_actions_for_context


def _as_signature(screen_or_sig: str) -> str:
    """Accept a 16-char menu_sig hex, or hash full screen text via menu_sig."""
    text = screen_or_sig or ""
    # menu_signature returns 16 hex chars; treat that shape as already hashed.
    if len(text) == 16 and all(c in "0123456789abcdef" for c in text):
        return text
    return menu_signature(text)


def dry_run_step(
    *,
    before_screen: str,
    after_screen: str | None = None,
    known_actions: list[str] | None = None,
    prior_rules: list[dict] | None = None,
    authority: str = "ai",
    human_combat_confirmed: bool = False,
    tried_action: str | None = None,
    expected_transition: str | None = None,
    prior_confidence: float = 0.0,
) -> dict:
    """One dry-run learning step: propose (and optionally verify).

    Returns a trace dict. Never sends keys. ``after_screen`` is optional
    — when omitted, the trace stops at the candidate plan (propose-only).
    When present (and ``tried_action`` set), includes a verify result.
    """
    before_sig = _as_signature(before_screen)
    blocked = blocked_actions_for_context(
        authority=authority,
        human_combat_confirmed=human_combat_confirmed,
    )
    candidates = propose_candidates(
        before_sig,
        known_actions=known_actions,
        prior_rules=prior_rules,
        blocked_actions=blocked,
    )
    trace: dict = {
        "mode": "dry_run",
        "before_signature": before_sig,
        "candidates": candidates,
        "selected_action": None,
        "verify": None,
        "proposed_rule_update": None,
        "executed": False,
    }
    if not candidates and tried_action is None:
        return trace

    selected = tried_action or (candidates[0]["action"] if candidates else None)
    trace["selected_action"] = selected

    if after_screen is None or selected is None:
        return trace

    after_sig = _as_signature(after_screen)
    verify = compare_transition(
        before_sig,
        after_sig,
        expected_transition=expected_transition,
        prior_confidence=prior_confidence,
    )
    trace["verify"] = verify
    # Proposed store update — caller may persist; this loop never writes.
    trace["proposed_rule_update"] = {
        "state_signature": before_sig,
        "tried_action": selected,
        "observed_transition": verify["observed_transition"],
        "confidence": verify["new_confidence"],
    }
    return trace
