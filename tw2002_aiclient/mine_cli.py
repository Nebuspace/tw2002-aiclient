"""``tw mine`` / ``tw patterns`` — candidate-mining CLI (WO-BUILD-WIRE-TW-MINE-CLI-VERB).

Filesystem-only: ranks recurring ledger subsequences and optionally writes
inert drafts under ``state/skills/_drafts/``. Never opens a session socket,
never sends. Lives outside ``session/cli.py`` for the same line-cap reason
as ``catalog_cli`` / ``players_cli`` / ``rules.cli``.
"""

from __future__ import annotations

import argparse
import json

from tw2002_aiclient import miner

__all__ = ["add_mine_parsers", "cmd_mine"]

# Match miner.py defaults (``_DEFAULT_MIN_SUPPORT`` / ``_DEFAULT_TOP_K``).
_DEFAULT_MIN_SUPPORT = 2
_DEFAULT_TOP_K = 3


def cmd_mine(args: argparse.Namespace) -> int:
    """Mine the trace ledger; optionally propose inert drafts. Never sends."""
    propose = not bool(getattr(args, "no_propose", False))
    top_k = int(getattr(args, "top_k", _DEFAULT_TOP_K))
    result = miner.mine_ledger(
        min_support=int(getattr(args, "min_support", _DEFAULT_MIN_SUPPORT)),
        top_k=top_k,
        ledger_path=getattr(args, "ledger", None),
        drafts_dir_path=getattr(args, "drafts", None),
        state_dir=getattr(args, "state_dir", None),
        world_id=getattr(args, "world_id", None),
        propose=propose,
    )
    patterns = result["patterns"]
    drafts = result["drafts"]
    if getattr(args, "json", False):
        payload = {
            "ok": True,
            "patterns": patterns,
            "drafts": drafts,
            "propose": propose,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(f"patterns={len(patterns)} drafts={len(drafts)}")
    for d in drafts:
        print(
            f"  draft {d['name']} support={d['support']} "
            f"cr/turn={d['cr_per_turn']} path={d['path']}"
        )
    for p in patterns[: max(0, top_k)]:
        print(
            f"  pattern inputs={p['inputs']} support={p['support']} "
            f"cr/turn={p['cr_per_turn']} cr/action={p['cr_per_action']}"
        )
    return 0


def add_mine_parsers(sub: argparse._SubParsersAction) -> None:
    """Register ``tw mine`` and alias ``tw patterns``."""
    help_text = (
        "mine the trace ledger for recurring profitable input subsequences "
        "(filesystem only; writes inert drafts, never sends)"
    )
    for verb in ("mine", "patterns"):
        sp = sub.add_parser(verb, help=help_text)
        sp.add_argument(
            "--ledger",
            default=None,
            metavar="PATH",
            help="ledger JSONL path (default: state/ledger.jsonl)",
        )
        sp.add_argument(
            "--drafts",
            default=None,
            metavar="PATH",
            help="inert drafts directory (default: state/skills/_drafts)",
        )
        sp.add_argument(
            "--state-dir",
            default=None,
            dest="state_dir",
            metavar="PATH",
            help="state root override (drafts default under this tree)",
        )
        sp.add_argument(
            "--world-id",
            default=None,
            dest="world_id",
            metavar="SLUG",
            help="stamp proposed drafts with this world_id when set",
        )
        sp.add_argument(
            "--min-support",
            type=int,
            default=_DEFAULT_MIN_SUPPORT,
            dest="min_support",
            metavar="N",
            help=f"minimum pattern support (default {_DEFAULT_MIN_SUPPORT})",
        )
        sp.add_argument(
            "--top-k",
            type=int,
            default=_DEFAULT_TOP_K,
            dest="top_k",
            metavar="N",
            help=f"propose at most N drafts (default {_DEFAULT_TOP_K})",
        )
        sp.add_argument(
            "--no-propose",
            action="store_true",
            help="rank only - do not write draft files",
        )
        sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
        sp.set_defaults(func=cmd_mine)
