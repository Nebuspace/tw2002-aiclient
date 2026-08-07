"""``tw teach analyze`` -- invoke the on-demand AI teacher (WO-BUILD-AI-TEACHER-ANALYZE-CLI).

Filesystem-only, like ``mine_cli`` / ``rules.cli``: reads the ledger, never
opens a session socket, never sends. Lives outside ``session/cli.py`` for the
same line-cap reason as ``mine_cli`` / ``catalog_cli`` / ``players_cli`` /
``rules.cli``.

There is no live daemon status surface this CLI verb can read from a cold
process, so the escalation "frame" is sourced from the most recent ledger
row's ``post_state`` (the settled screen state after the last recorded send)
unless the operator points at a captured frame with ``--frame-file``. This is
a judgment call, not a canon citation -- flagged for review.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys

from . import ai_teacher, ledger

__all__ = ["add_teach_parser", "cmd_teach_analyze"]

_DEFAULT_BACKEND = "tw2002_aiclient.ai_teacher:no_backend_configured"


def _resolve_backend(dotted: str) -> ai_teacher.AnalyzeBackend:
    module_name, _, attr = dotted.partition(":")
    if not module_name or not attr:
        raise ValueError(f"--backend must be 'module:function', got {dotted!r}")
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def _frame_from_ledger(entries: list[dict]) -> dict:
    if not entries:
        return {}
    return dict(entries[-1].get("post_state") or {})


def cmd_teach_analyze(args: argparse.Namespace) -> int:
    """Run one on-demand Analyze pass. Exit 0 whether declined or drafted."""
    entries = ledger.read_entries(getattr(args, "ledger", None), world_id=getattr(args, "world_id", None))

    if getattr(args, "frame_file", None):
        with open(args.frame_file, encoding="utf-8") as fh:
            frame = json.load(fh)
    else:
        frame = _frame_from_ledger(entries)

    context = ai_teacher.gather_escalation_context(frame, entries)

    try:
        backend = _resolve_backend(getattr(args, "backend", _DEFAULT_BACKEND))
    except (ImportError, AttributeError, ValueError) as exc:
        print(f"ERROR: could not resolve --backend: {exc}", file=sys.stderr)
        return 1

    try:
        result = ai_teacher.analyze_escalation(
            context,
            backend,
            state_dir=getattr(args, "state_dir", None),
            world_id=getattr(args, "world_id", None),
        )
    except ai_teacher.AITeacherBackendNotConfigured as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}))
        else:
            print(f"ERROR: {exc}")
        return 1

    if getattr(args, "json", False):
        print(json.dumps({"ok": True, **result}, sort_keys=True))
        return 0

    if result["declined"]:
        print(f"declined: {result['reason']}")
    else:
        print(f"draft written: {result['draft']}")
        print("inert -- it cannot fire until you run: tw rule approve <rule_id>")
    return 0


def add_teach_parser(sub: argparse._SubParsersAction) -> None:
    """Register ``tw teach analyze`` onto an existing subparser action."""
    sp_teach = sub.add_parser(
        "teach",
        help="invoke the on-demand AI teacher (retrospective, human-invoked)",
        description=(
            "Ask the AI teacher to Analyze one escalation moment and propose "
            "an inert rule draft. The AI never sends a keystroke -- it only "
            "ever writes through the same draft-and-approve gate as every "
            "other rule author."
        ),
    )
    teach_sub = sp_teach.add_subparsers(dest="teach_cmd", metavar="{analyze}")
    sp_teach.set_defaults(func=lambda _: (sp_teach.print_help() or 0), state_dir=None, json=False)

    sp = teach_sub.add_parser(
        "analyze",
        help="propose a draft rule for the last escalation moment",
        description=(
            "Read the recent ledger + a frame source and ask the AI-teacher "
            "backend for a proposed rule. Writes an inert draft, or declines "
            "and reports why -- never approves, never sends."
        ),
    )
    sp.add_argument("--session", dest="world_id", default=None, metavar="ID", help="world/session id (ledger filter)")
    sp.add_argument("--ledger", default=None, metavar="PATH", help="ledger JSONL path (default: state/ledger.jsonl)")
    sp.add_argument(
        "--frame-file",
        dest="frame_file",
        default=None,
        metavar="PATH",
        help="JSON file with the parsed screen state to analyze (default: last ledger row's post_state)",
    )
    sp.add_argument(
        "--backend",
        default=_DEFAULT_BACKEND,
        metavar="MODULE:FUNC",
        help="dotted import path to an AnalyzeBackend callable "
        f"(default: {_DEFAULT_BACKEND}, which always raises -- no model wired yet)",
    )
    sp.add_argument("--state-dir", dest="state_dir", default=None, help="override the state/ root")
    sp.add_argument("--json", action="store_true", help="machine-readable output")
    sp.set_defaults(func=cmd_teach_analyze)
