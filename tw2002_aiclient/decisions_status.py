"""DECISIONS panel producer — ``status["autopilot_trace"]`` dry-run (display only).

``cockpit/decisions.py`` is a starved consumer: it only renders
``status["autopilot_trace"]`` and never builds one. This module is the
producer. It never sends, never arms, and never invents a money-path.

Shares the FOCUS candidate set (``recommend_focus_candidates`` /
``status["focus"]["candidates"]``) but emits the archived dry-run field
names ``ev_cr_per_turn`` + short ``rationale`` strings. ``chosen`` is the
first ungated candidate in FOCUS order — a dry-run bookkeeping pick for
display, not a live keystroke.

Canon: `canon/surfaces/trainer-cockpit.md` DECISIONS pane;
`cockpit/decisions.py` status-dict field mapping.
"""

from __future__ import annotations

__all__ = ["DecisionScalars", "build_autopilot_trace", "AUTOPILOT_TRACE_KEY"]

from tw2002_aiclient.chain_status import ChainScalars
from tw2002_aiclient.focus_status import FOCUS_KEY, recommend_focus_candidates

AUTOPILOT_TRACE_KEY = "autopilot_trace"

_RATIONALE_BY_KIND = {
    "run_chain": "priced executable cycle",
    "explore": "map / catalog work remaining",
    "upgrade": "upgrade EV vs stay trading",
}


def _rationale_for(cand: dict) -> str | None:
    kind = cand.get("kind")
    if not isinstance(kind, str):
        return None
    if cand.get("gated"):
        reason = cand.get("gate_reason")
        return reason if isinstance(reason, str) and reason else None
    weight = cand.get("priority_weight")
    if isinstance(weight, int) and weight > 0 and kind == "explore":
        return f"catalog weight {weight}"
    return _RATIONALE_BY_KIND.get(kind)


def _trace_candidate(cand: dict) -> dict:
    """Map a FOCUS candidate dict → DECISIONS ``autopilot_trace`` candidate."""
    ev = cand.get("ev_per_turn")
    if isinstance(ev, bool) or not isinstance(ev, (int, float)):
        ev_out: float | None = None
    else:
        ev_out = float(ev)
    gated = bool(cand.get("gated"))
    reason = cand.get("gate_reason")
    return {
        "kind": cand.get("kind") if isinstance(cand.get("kind"), str) else None,
        "ev_cr_per_turn": ev_out,
        "gated": gated,
        "gate_reason": reason if isinstance(reason, str) else None,
        "rationale": _rationale_for(cand),
    }


def build_autopilot_trace(
    status: object,
    *,
    chain_scalars: ChainScalars | None = None,
) -> dict:
    """Assemble ``{chosen, candidates}`` from FOCUS-ranked candidates.

    Never raises. Prefer ``status["focus"]["candidates"]`` when already
    merged (cheap); otherwise call ``recommend_focus_candidates``.
    """
    try:
        if not isinstance(status, dict):
            return {"chosen": None, "candidates": []}
        status_d = status
        focus = status_d.get(FOCUS_KEY)
        raw: list = []
        if isinstance(focus, dict):
            cands = focus.get("candidates")
            if isinstance(cands, list):
                raw = [c for c in cands if isinstance(c, dict)]
        if not raw:
            raw = recommend_focus_candidates(
                status_d, chain_scalars=chain_scalars
            )
        candidates = [_trace_candidate(c) for c in raw]
        chosen = None
        for c in candidates:
            if c.get("kind") and not c.get("gated"):
                chosen = c["kind"]
                break
        return {"chosen": chosen, "candidates": candidates}
    except Exception:  # noqa: BLE001 — producer must never break the draw path
        return {"chosen": None, "candidates": []}


class DecisionScalars:
    """Merges ``status["autopilot_trace"]``. Draw-path cheap; never clobbers."""

    def __init__(self, chain_scalars: ChainScalars | None = None) -> None:
        self._chain_scalars = chain_scalars

    def bind(self, chain_scalars: ChainScalars | None) -> None:
        self._chain_scalars = chain_scalars

    def merge(self, status: object) -> dict | None:
        if not isinstance(status, dict):
            return status
        if status.get(AUTOPILOT_TRACE_KEY) is not None:
            return status
        merged = dict(status)
        merged[AUTOPILOT_TRACE_KEY] = build_autopilot_trace(
            merged, chain_scalars=self._chain_scalars
        )
        return merged

    def wrap(self, provider):
        if provider is None:
            return None

        def _merged():
            return self.merge(provider())

        return _merged
