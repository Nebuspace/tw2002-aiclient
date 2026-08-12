"""``tw coach`` — strategy-card KB + teaching-provenance coverage CLI.

``show`` is filesystem-only over ``data/coach/strategies.json`` (never a
session socket). ``provenance`` is a separate read-only rule-store surface
for the teaching-provenance coverage axis
(``coverage_metrics.teaching_provenance_counts``) — WO-BUILD-COVERAGE-METRICS-
TEACHING-PROVENANCE-WIRE.

Lives outside ``session/cli.py`` for the same line-cap reason as
``catalog_cli`` / ``mine_cli`` / ``players_cli``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tw2002_aiclient import coach_kb
from tw2002_aiclient.coverage_metrics import (
    format_teaching_provenance_line,
    teaching_provenance_counts,
    teaching_provenance_share,
)
from tw2002_aiclient.rules.store import read_rule_store

__all__ = ["add_coach_parsers", "cmd_coach_provenance", "cmd_coach_show"]


def _strategies_path(args: argparse.Namespace) -> Path:
    raw = getattr(args, "strategies", None)
    if raw:
        return Path(raw)
    return coach_kb.default_kb_paths()[0]


def _card_to_dict(card: coach_kb.StrategyCard) -> dict[str, Any]:
    return {
        "id": card.id,
        "title": card.title,
        "what": card.what,
        "when_trigger": card.when_trigger,
        "tradeoffs": list(card.tradeoffs),
        "steps": list(card.steps),
        "okf_refs": list(card.okf_refs),
        "hypothesis_flags": list(card.hypothesis_flags),
        "priority": card.priority,
    }


def _print_card_text(card: coach_kb.StrategyCard) -> None:
    title = card.title
    if card.hypothesis_flags:
        title = f"{title} (unverified)"
    print(f"{title}  [{card.id}]")
    print(f"  when: {card.when_trigger}   priority: {card.priority}")
    if card.what:
        print(f"  what: {card.what}")
    if card.tradeoffs:
        print("  tradeoffs:")
        for t in card.tradeoffs:
            print(f"    - {t}")
    if card.steps:
        print("  steps:")
        for i, s in enumerate(card.steps, start=1):
            print(f"    {i}. {s}")
    if card.okf_refs:
        print("  okf_refs:")
        for ref in card.okf_refs:
            print(f"    - {ref}")
    if card.hypothesis_flags:
        print(f"  hypothesis_flags: {', '.join(card.hypothesis_flags)}")


def _print_list_text(cards: tuple[coach_kb.StrategyCard, ...]) -> None:
    for card in cards:
        flag = " (unverified)" if card.hypothesis_flags else ""
        print(
            f"{card.id:<20} {card.when_trigger:<18} priority={card.priority:<3} "
            f"{card.title}{flag}"
        )


def cmd_coach_show(args: argparse.Namespace) -> int:
    """``tw coach show [id]`` — full authored card, incl. tradeoffs/okf_refs.

    No ``id`` lists every card (brief). A given ``id`` prints that one card's
    complete authored content. Never renders into the DECISIONS gutter — this
    is a standalone, filesystem-only read.
    """
    path = _strategies_path(args)
    as_json = bool(getattr(args, "json", False))
    try:
        kb = coach_kb.load_coach_kb(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        err = {"ok": False, "error": type(exc).__name__, "detail": str(exc)}
        if as_json:
            print(json.dumps(err))
        else:
            print(f"coach show: could not load {path} — {type(exc).__name__}: {exc}")
        return 1

    card_id = getattr(args, "id", None)
    if card_id is None:
        if as_json:
            print(json.dumps({"ok": True, "cards": [_card_to_dict(c) for c in kb.strategies]}))
        else:
            _print_list_text(kb.strategies)
        return 0

    card = next((c for c in kb.strategies if c.id == card_id), None)
    if card is None:
        err = {"ok": False, "error": "unknown_id", "id": card_id}
        if as_json:
            print(json.dumps(err))
        else:
            print(f"coach show: unknown strategy card id {card_id!r}")
        return 1

    if as_json:
        print(json.dumps({"ok": True, "card": _card_to_dict(card)}))
    else:
        _print_card_text(card)
    return 0


def cmd_coach_provenance(args: argparse.Namespace) -> int:
    """``tw coach provenance`` — teaching-provenance axis over approved rules.

    Read-only rule-store consumer. Never sends. Never touches live covermeter.
    """
    as_json = bool(getattr(args, "json", False))
    state_raw = getattr(args, "state_dir", None)
    state_dir = Path(state_raw) if state_raw else None
    world_id = getattr(args, "world_id", None)
    try:
        store = read_rule_store(state_dir=state_dir, world_id=world_id)
    except Exception as exc:  # noqa: BLE001 — CLI fail-closed message
        err = {"ok": False, "error": type(exc).__name__, "detail": str(exc)}
        if as_json:
            print(json.dumps(err))
        else:
            print(f"coach provenance: {type(exc).__name__}: {exc}")
        return 1

    rules = store.get("rules") if isinstance(store, dict) else None
    if not isinstance(rules, list):
        err = {
            "ok": False,
            "error": "unreadable_store",
            "status": store.get("status") if isinstance(store, dict) else None,
        }
        if as_json:
            print(json.dumps(err))
        else:
            print(f"coach provenance: unreadable store (status={err['status']!r})")
        return 1

    counts = teaching_provenance_counts(rules)
    share = teaching_provenance_share(counts)
    if as_json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "counts": dict(counts),
                    "ai_share": share,
                    "store_status": store.get("status"),
                }
            )
        )
    else:
        print(format_teaching_provenance_line(counts))
        status = store.get("status")
        if status and status != "ok":
            print(f"(rule store status: {status})")
    return 0


def add_coach_parsers(sub: argparse._SubParsersAction) -> None:
    """Register ``tw coach show`` and ``tw coach provenance``."""
    sp_coach = sub.add_parser(
        "coach",
        help=(
            "strategy-card KB (show) + teaching-provenance coverage axis "
            "(provenance)"
        ),
    )
    coach_sub = sp_coach.add_subparsers(dest="coach_verb")

    sp_show = coach_sub.add_parser(
        "show",
        help="show one strategy card in full, or list all cards when id is omitted",
    )
    sp_show.add_argument(
        "id",
        nargs="?",
        default=None,
        help="strategy card id, e.g. pair_trade_loop (omit to list all)",
    )
    sp_show.add_argument(
        "--strategies",
        default=None,
        metavar="PATH",
        help="strategies.json override",
    )
    sp_show.add_argument(
        "--json",
        action="store_true",
        help="machine-parseable JSON (full card fields incl. tradeoffs/okf_refs)",
    )
    sp_show.set_defaults(func=cmd_coach_show)

    sp_prov = coach_sub.add_parser(
        "provenance",
        help="teaching-provenance axis over approved rules (human / ai-approved / unknown)",
    )
    sp_prov.add_argument(
        "--state-dir",
        default=None,
        metavar="PATH",
        help="override state/ root (default: project state/)",
    )
    sp_prov.add_argument(
        "--world-id",
        default=None,
        metavar="ID",
        help="world-scoped rules/ subdirectory when present",
    )
    sp_prov.add_argument(
        "--json",
        action="store_true",
        help="machine-parseable JSON counts + ai_share",
    )
    sp_prov.set_defaults(func=cmd_coach_provenance)
