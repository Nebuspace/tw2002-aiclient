"""Teaching-provenance coverage axis (canon/engine/coverage-metrics.md).

The live App-vs-Human share lives in :mod:`tw2002_aiclient.cockpit.covermeter`
and :func:`tw2002_aiclient.ledger.live_actor_counts`. This module is the
**separate third axis**: of the guarded rules the app can play, how many were
authored by a human vs AI-drafted-then-human-approved vs legacy/unknown.

It never folds into the live coverage ratio and never drives a keystroke.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from tw2002_aiclient.rule_engine import (
    ORIGIN_AI_APPROVED,
    ORIGIN_HUMAN,
    Rule,
)

__all__ = [
    "ORIGIN_BUCKET_UNKNOWN",
    "format_teaching_provenance_line",
    "teaching_provenance_counts",
    "teaching_provenance_share",
]

# Metrics bucket for rules whose documents predate the ``origin`` field (or
# carry a null/absent value). Not a valid on-disk ``origin`` string.
ORIGIN_BUCKET_UNKNOWN = "unknown"


def _as_rule(item: Any) -> Rule | None:
    if isinstance(item, Rule):
        return item
    return None


def teaching_provenance_counts(rules: Iterable[Any]) -> dict[str, int]:
    """Count **approved** (playable) rules by teaching origin.

    Returns ``{"human": N, "ai-approved": N, "unknown": N, "total": N}``.
    Drafts and other unapproved documents are excluded — they are not yet
    app-playable repertoire (canon example counts only rules the app can play).

    An approved rule with ``origin is None`` (legacy store) lands in
    ``unknown``, never silently in ``human`` or ``ai-approved``.
    """
    human = 0
    ai_approved = 0
    unknown = 0
    for item in rules:
        rule = _as_rule(item)
        if rule is None or not rule.approved:
            continue
        if rule.origin == ORIGIN_HUMAN:
            human += 1
        elif rule.origin == ORIGIN_AI_APPROVED:
            ai_approved += 1
        else:
            unknown += 1
    return {
        ORIGIN_HUMAN: human,
        ORIGIN_AI_APPROVED: ai_approved,
        ORIGIN_BUCKET_UNKNOWN: unknown,
        "total": human + ai_approved + unknown,
    }


def teaching_provenance_share(counts: Mapping[str, int]) -> float | None:
    """AI teaching contribution share among playable rules, or ``None`` if empty.

    Canon: ``AI teaching contribution = count (or share) of guarded rules the
    AI drafted that the human approved``. Share is ``ai-approved / total``;
    ``None`` when ``total == 0`` (undefined, same honesty as live ``0/0``).
    """
    total = int(counts.get("total", 0) or 0)
    if total <= 0:
        return None
    ai = int(counts.get(ORIGIN_AI_APPROVED, 0) or 0)
    return ai / total


def format_teaching_provenance_line(counts: Mapping[str, int]) -> str:
    """One-line operator digest of the teaching-provenance axis.

    Never invents a share when ``total == 0`` — prints ``ai-share=?`` instead.
    """
    human = int(counts.get(ORIGIN_HUMAN, 0) or 0)
    ai = int(counts.get(ORIGIN_AI_APPROVED, 0) or 0)
    unknown = int(counts.get(ORIGIN_BUCKET_UNKNOWN, 0) or 0)
    total = int(counts.get("total", 0) or 0)
    share = teaching_provenance_share(counts)
    share_txt = f"{share:.0%}" if share is not None else "?"
    return (
        f"teaching provenance (approved rules): "
        f"human={human}  ai-approved={ai}  unknown={unknown}  "
        f"total={total}  ai-share={share_txt}"
    )
