"""Session-retro analyzer (TW-12 / DESIGN-v2 §15.6) — pure client-side.

`tw analyze <session>` reads a ledger slice, reuses the Trace-Ledger miner
to group recurring input patterns, and ranks profitable ones as
"candidates to codify." v1 has no `actor`/`session_id` fields yet (TW-05);
session is a soft key: capture name, ISO-ts prefix, or `all`.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from .ledger import read_entries
from .miner import mine_patterns


def select_session_entries(
    entries: Sequence[dict],
    session: str,
) -> list[dict]:
    """Slice the ledger for a named session without TW-05 session_id.

    Match order:
    1. Exact `capture` field (named `tw record` window).
    2. ISO timestamp prefix (e.g. ``2026-07-19`` or ``2026-07-19T15``).
    3. ``all`` / ``*`` → entire ledger.
    """
    key = (session or "").strip()
    if not key:
        return []
    if key in ("all", "*"):
        return list(entries)

    by_capture = [e for e in entries if e.get("capture") == key]
    if by_capture:
        return by_capture

    by_ts = [e for e in entries if str(e.get("ts") or "").startswith(key)]
    return by_ts


def _rank_score(pattern: dict) -> tuple:
    cr_turn = pattern.get("cr_per_turn")
    cr_action = pattern.get("cr_per_action") or 0.0
    support = pattern.get("support") or 0
    # Prefer patterns that both recur and pay; turn-rate first when known.
    return (
        cr_turn if cr_turn is not None else float("-inf"),
        cr_action * support,
        support,
    )


def analyze_session(
    session: str,
    *,
    entries: Optional[Sequence[dict]] = None,
    min_support: int = 2,
    ledger_path=None,
    top_k: int = 20,
) -> dict[str, Any]:
    """Return a session-retro report suitable for CLI / JSON output."""
    all_entries = list(entries) if entries is not None else read_entries(ledger_path)
    sliced = select_session_entries(all_entries, session)
    patterns = mine_patterns(entries=sliced, min_support=min_support) if sliced else []

    profitable = [
        p
        for p in patterns
        if (p.get("cr_per_turn") or 0) > 0 or (p.get("cr_per_action") or 0) > 0
    ]
    profitable.sort(key=_rank_score, reverse=True)
    candidates = profitable[:top_k]

    total_cr = sum((e.get("reward") or {}).get("d_credits") or 0 for e in sliced)
    return {
        "session": session,
        "entry_count": len(sliced),
        "ledger_total": len(all_entries),
        "match": (
            "all"
            if session.strip() in ("all", "*")
            else "capture"
            if any(e.get("capture") == session.strip() for e in sliced)
            else "ts_prefix"
            if sliced
            else "none"
        ),
        "total_d_credits": total_cr,
        "pattern_count": len(patterns),
        "candidates": [
            {
                "rank": i + 1,
                "support": c["support"],
                "cr_per_turn": c.get("cr_per_turn"),
                "cr_per_action": c.get("cr_per_action"),
                "inputs": c["inputs"],
                "pre_class": c.get("pre_class"),
                "post_class": c.get("post_class"),
                "note": "recurring profitable — candidate to codify as trainer behavior",
            }
            for i, c in enumerate(candidates)
        ],
        "note": (
            "v1 has no actor/session_id (TW-05); filter is capture-name or "
            "timestamp-prefix. AI vs trainer split sharpens after TW-05."
        ),
    }


def format_report(report: dict) -> str:
    """Human-readable multi-line summary for `tw analyze` (non-JSON)."""
    lines = [
        f"session-retro: {report['session']!r}  "
        f"[{report['match']}]  entries={report['entry_count']}/"
        f"{report['ledger_total']}  ΣΔcr={report['total_d_credits']:+d}",
        report["note"],
        "",
    ]
    if report["entry_count"] == 0:
        lines.append("(no ledger entries matched — try a capture name, date prefix, or 'all')")
        return "\n".join(lines)
    if not report["candidates"]:
        lines.append(
            f"(no profitable recurring patterns at this support — "
            f"{report['pattern_count']} raw pattern(s) found)"
        )
        return "\n".join(lines)

    lines.append("candidates to codify (profit × frequency):")
    for c in report["candidates"]:
        cr_t = c["cr_per_turn"]
        rate = f"{cr_t:.1f} cr/turn" if cr_t is not None else f"{c['cr_per_action']:.1f} cr/action"
        steps = " → ".join(repr(i) for i in c["inputs"])
        lines.append(
            f"  #{c['rank']}  n={c['support']}  {rate}  "
            f"[{c.get('pre_class')}→{c.get('post_class')}]  {steps}"
        )
    return "\n".join(lines)
