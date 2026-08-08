"""The on-demand, human-invoked retrospective AI teacher — ``Screen Analyze``.

Canon: ``canon/engine/ai-teacher.md``. The AI is a third role, distinct from
the trainer's two live keystroke senders (``app`` / ``human``): it is a
*rule author*, never a driver. Its entire product is a proposed
``when -> do`` rule document that is always written as an inert **draft**
(``approved: False``) through :func:`tw2002_aiclient.rules.writer.write_draft`
-- the only function in the product that can persist a rule at all, and one
that has no parameter through which a caller could ask for ``approved: True``.

This module has **no live-send path**. It never opens a socket, never calls
``Session.send``, never shells out. It reads an escalation moment
(the settled screen state plus recent ledger rows), calls an injectable
backend for a proposed rule shape, and either declines (per the ethos bound
below) or hands the proposal to ``write_draft`` -- which validates it through
the kernel's own strict parser and applies its own ``refuse_pvp_aggression_rule``
check before anything reaches disk.

The ethos bound is checked here too, explicitly, before ``write_draft`` is
ever called: canon requires the teacher itself to *decline to author* a rule
that would initiate PvP, exploit, or collude, and to report that decline --
not merely rely on the writer's internal refusal to silently fail. Both
checks call the same :func:`tw2002_aiclient.alignment_gate.refuse_pvp_aggression_rule`,
so there is exactly one denylist, checked twice at two different moments for
two different reasons (teacher-declines vs writer-refuses).
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from .alignment_gate import AlignmentRefusal, refuse_pvp_aggression_rule
from .rules.writer import write_draft

__all__ = [
    "AITeacherBackendNotConfigured",
    "AnalyzeBackend",
    "analyze_escalation",
    "gather_escalation_context",
    "no_backend_configured",
]

_DEFAULT_WINDOW = 10


class AITeacherBackendNotConfigured(Exception):
    """No AI-teacher backend is wired.

    Wiring a real model client is a separate WO -- this module deliberately
    adds no LLM SDK dependency. The backend is an injectable seam
    (:class:`AnalyzeBackend`) so the draft-and-approve, ethos-bound plumbing
    can be built and proven before any model is chosen.
    """


class AnalyzeBackend(Protocol):
    """A callable that turns an escalation context into a raw draft dict."""

    def __call__(self, context: dict) -> dict: ...


def no_backend_configured(context: dict) -> dict:
    """The default backend. Always raises -- there is no model wired yet."""
    raise AITeacherBackendNotConfigured(
        "no AI-teacher backend configured -- wiring a real model client is a separate WO"
    )


def gather_escalation_context(
    status_response: dict,
    ledger_entries: list[dict] | None = None,
    *,
    window: int = _DEFAULT_WINDOW,
) -> dict:
    """Bundle one escalation moment into the context a backend reads.

    Pure and I/O-free: the caller resolves ``status_response`` and
    ``ledger_entries`` (e.g. via :func:`tw2002_aiclient.ledger.read_entries`)
    and hands them in, so this function stays testable without a filesystem
    or a live daemon.
    """
    recent = list(ledger_entries)[-window:] if ledger_entries else []
    return {"frame": status_response, "recent_ledger": recent}


def analyze_escalation(
    context: dict,
    backend: AnalyzeBackend,
    *,
    state_dir=None,
    world_id: str | None = None,
) -> dict:
    """Run one on-demand Analyze pass. Never sends a keystroke.

    Returns ``{"declined": True, "reason": ...}`` when the ethos bound
    refuses to author the proposed rule, or ``{"declined": False, "draft":
    <path write_draft wrote>}`` once the (inert) draft is persisted. A
    malformed backend response is not swallowed -- ``write_draft``'s own
    strict validation is the final gate and its error propagates.
    """
    raw = backend(context)
    if not isinstance(raw, Mapping):
        raise TypeError(f"AI-teacher backend must return a mapping, got {type(raw).__name__}")

    document: dict[str, Any] = {
        "rule_id": raw["rule_id"],
        "screen_match": raw["when"],
        "do": raw["do"],
        "priority": raw["priority"],
        "scope": raw.get("scope", "one-shot"),
        "guards": raw.get("guards", []),
        # Teaching provenance: AI-authored draft (becomes repertoire on approve).
        "origin": "ai-approved",
    }

    try:
        refuse_pvp_aggression_rule(document)
    except AlignmentRefusal as exc:
        return {"declined": True, "reason": str(exc)}

    path = write_draft(document, state_dir=state_dir, world_id=world_id)
    return {"declined": False, "draft": str(path)}
