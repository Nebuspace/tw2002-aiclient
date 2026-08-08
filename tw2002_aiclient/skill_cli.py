"""``tw skill approve`` — promote a mined skills draft (WO-WIRE-MINED-SKILLS-PROMOTE-CLI).

Mirrors ``rules.cli``'s ``tw rule approve``: the only product caller of
``loops.recorder.promote_draft``. Filesystem-only; never sends.
"""

from __future__ import annotations

import argparse
import json
import sys

from tw2002_aiclient.loops.recorder import LoopWriteError, promote_draft

__all__ = ["add_skill_parser"]


def cmd_skill_approve(args: argparse.Namespace) -> int:
    """Promote one draft into the blessed skills library. **The human act.**"""
    try:
        path = promote_draft(
            args.name,
            state_dir=getattr(args, "state_dir", None),
            world_id=getattr(args, "world_id", None),
        )
    except (LoopWriteError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "path": str(path), "promoted": True}))
        return 0
    print(f"promoted: {args.name}")
    print(f"  {path}")
    return 0


def add_skill_parser(sub: argparse._SubParsersAction) -> None:
    """Wire ``skill approve`` onto an existing subparser action."""
    sp_skill = sub.add_parser(
        "skill",
        help=(
            "promote mined/AI skill drafts into the blessed library "
            "(filesystem only; never sends)"
        ),
    )
    skill_sub = sp_skill.add_subparsers(dest="skill_verb")
    sp_skill.set_defaults(
        func=lambda _: (sp_skill.print_help() or 0),
        json=False,
    )

    sp = skill_sub.add_parser(
        "approve",
        help="promote one draft under state/skills/_drafts into the blessed store",
    )
    sp.add_argument("name", help="draft macro name (document 'name' field)")
    sp.add_argument(
        "--world-id",
        default=None,
        dest="world_id",
        metavar="SLUG",
        help="world-scoped store under state/world/<slug>/skills",
    )
    sp.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    sp.set_defaults(func=cmd_skill_approve)
