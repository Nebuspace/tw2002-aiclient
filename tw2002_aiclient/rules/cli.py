"""``tw rule draft`` / ``tw rule approve`` -- the operator's two verbs.

Lives here rather than in ``session/cli.py`` for two reasons. It touches only
the filesystem, so routing it through the daemon's request/response plumbing
would buy nothing and cost a running daemon; and ``session/cli.py`` is already
over the project's line cap (#218), so the wiring there stays at the parser
declarations while the behaviour sits in the package that owns the store. The
import direction matches the one ``loops/store.py`` protects -- this package
imports nothing from ``session/``.

Why ``draft`` takes a JSON document rather than one flag per field
-----------------------------------------------------------------
A rule's ``guards`` are a **list whose order is authored content**: the kernel
reports *"the first failing stop guard in the rule's own declared order"* and
says in as many words that the order is *"not an accident of how the caller
happened to assemble the document"*. Two repeatable flags (``--guard`` /
``--stop-guard``) would make it exactly that accident, because argparse
collects each ``dest`` separately and the interleaving an operator typed is
gone by the time the handler runs. A single flag with an invented
``fact:op:value:posture:reason`` grammar fares no better -- five fields, one of
them free text that may contain the separator.

So the guarded case is expressed in the schema it already has. The eventual
author here is the AI teacher, which emits JSON rather than shell words, and
the operator keeps a flag shorthand for the guard-less rule that is most of
what a human types by hand.

Neither path can approve anything. ``draft`` writes through
:func:`~tw2002_aiclient.rules.writer.write_draft`, which has no parameter for
it; ``approve`` is the only caller of :func:`promote_draft` and exists to be
typed deliberately.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .store import read_rule_store, resolve_roots
from .writer import RuleWriteError, promote_draft, write_draft

__all__ = ["add_rule_parser", "cmd_rule_approve", "cmd_rule_draft", "cmd_rule_list"]

_SHORTHAND = ("rule_id", "screen_match", "do", "priority")


def _document_from_args(args) -> dict:
    """The document to write, from ``--from-file``/stdin or the shorthand flags.

    Raises :class:`RuleWriteError` for a source this handler cannot turn into a
    document at all. Everything about whether the document is a *valid rule* is
    left to the writer, which asks the kernel parser -- there is deliberately
    no second opinion here.
    """
    source = getattr(args, "from_file", None)
    if source is not None:
        try:
            raw = sys.stdin.read() if str(source) == "-" else Path(source).read_text(encoding="utf-8")
        except OSError as exc:
            raise RuleWriteError(f"could not read {source}: {exc.strerror or exc}") from None
        try:
            return json.loads(raw)
        except ValueError as exc:
            raise RuleWriteError(f"{source} is not valid JSON: {exc}") from None

    missing = [f for f in _SHORTHAND if getattr(args, f, None) is None]
    if missing:
        raise RuleWriteError(
            "give --from-file (or - for stdin), or all of "
            + ", ".join("--" + f.replace("_", "-") for f in _SHORTHAND)
            + f" (missing: {', '.join(missing)})"
        )
    document = {f: getattr(args, f) for f in _SHORTHAND}
    if getattr(args, "scope", None) is not None:
        document["scope"] = args.scope
    return document


def cmd_rule_draft(args) -> int:
    """Write one inert draft. Exit 0 on write, 1 on refusal.

    A refusal IS an error here, unlike ``tw reflex``'s STOP: the operator asked
    for something to be persisted and nothing was. Nothing partial is left
    behind either -- the writer validates before it opens a file.
    """
    try:
        document = _document_from_args(args)
        path = write_draft(
            document,
            state_dir=getattr(args, "state_dir", None),
            world_id=getattr(args, "world_id", None),
        )
    except RuleWriteError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "path": str(path), "approved": False}))
        return 0
    print(f"draft written: {path}")
    # Said every time, because "it wrote successfully" is the moment an author
    # is most likely to assume the rule is now live.
    print("inert — it cannot fire until you run: tw rule approve <rule_id>")
    return 0


def cmd_rule_approve(args) -> int:
    """Promote one draft into the blessed library. **The human act.**

    The only caller of :func:`promote_draft` in the product. Everything about
    this handler is meant to be typed on purpose: the rule_id is positional, it
    names one rule, and there is no ``--all``.
    """
    try:
        path = promote_draft(
            args.rule_id,
            state_dir=getattr(args, "state_dir", None),
            world_id=getattr(args, "world_id", None),
        )
    except RuleWriteError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "path": str(path), "approved": True}))
        return 0
    print(f"approved: {args.rule_id}")
    print(f"  {path}")
    return 0


def cmd_rule_list(args) -> int:
    """Show what is blessed and what is waiting, as two separate lists.

    Renders ``status`` rather than only counts: an empty library, a library
    that was never written, and a library we were not allowed to read are three
    different things to tell an operator, and the store keeps them distinct
    precisely so this does not flatten them.
    """
    state_dir = getattr(args, "state_dir", None)
    report = read_rule_store(
        state_dir=state_dir,
        include_drafts=True,
        world_id=getattr(args, "world_id", None),
    )
    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "ok": True,
                    "status": report["status"],
                    "rules": [r.rule_id for r in report["rules"]],
                    "drafts": [r.rule_id for r in report["drafts"]],
                    "unreadable": report["unreadable"],
                }
            )
        )
        return 0

    blessed, drafts_root = resolve_roots(
        state_dir=state_dir, world_id=getattr(args, "world_id", None)
    )
    print(f"store: {blessed}  ({report['status']})")
    for rule in report["rules"]:
        print(f"  approved  {rule.rule_id}  {rule.screen_match} -> {rule.do}  p{rule.priority}")
    for rule in report["drafts"]:
        print(f"  draft     {rule.rule_id}  {rule.screen_match} -> {rule.do}  p{rule.priority}")
    if not report["rules"] and not report["drafts"]:
        print("  (no rules)")
    for bad in report["unreadable"]:
        print(f"  UNREADABLE {bad['path']}: {bad['reason']}", file=sys.stderr)
    if report["drafts"]:
        print(f"drafts live in {drafts_root} and cannot fire until approved")
    return 0


def add_rule_parser(sub) -> None:
    """Wire ``rule draft|approve|list`` onto an existing subparser action.

    Kept here so ``session/cli.py`` gains three lines rather than a hundred.
    Mirrors the ``explore`` verb's nested shape, including its bare-verb help
    default.
    """
    sp_rule = sub.add_parser(
        "rule",
        help="author and approve taught reflex rules",
        description=(
            "Write inert rule drafts and promote them. A draft can never fire; "
            "'rule approve' is the only path to an approved rule."
        ),
    )
    rule_sub = sp_rule.add_subparsers(dest="rule_cmd", metavar="{draft,approve,list}")
    sp_rule.set_defaults(func=lambda _: (sp_rule.print_help() or 0), state_dir=None, json=False)

    sp = rule_sub.add_parser(
        "draft",
        help="write an inert rule draft under state/rules/_drafts/",
        description=(
            "Validate a rule document and persist it as a draft. Drafts are "
            "inert: the reflex layer does not read them and they cannot fire."
        ),
    )
    sp.add_argument(
        "--from-file",
        metavar="PATH",
        help="read the rule document as JSON from PATH, or '-' for stdin "
        "(the only form that can express guards, whose order is significant)",
    )
    sp.add_argument("--rule-id", dest="rule_id", help="unique id; also the filename stem")
    sp.add_argument("--screen", dest="screen_match", help="screen class this rule answers")
    sp.add_argument("--do", dest="do", help="macro name to propose")
    sp.add_argument("--priority", type=int, help="higher wins; ties are a STOP, not a coin flip")
    sp.add_argument("--scope", help="one-shot (default) or repeating")
    sp.add_argument("--state-dir", dest="state_dir", help="override the state/ root")
    sp.add_argument(
        "--world-id",
        dest="world_id",
        default=None,
        metavar="SLUG",
        help="world-scoped store under state/world/<slug>/rules (migrates flat on first I/O)",
    )
    sp.add_argument("--json", action="store_true", help="machine-readable output")
    sp.set_defaults(func=cmd_rule_draft)

    sp = rule_sub.add_parser(
        "approve",
        help="promote one draft into the approved library (the human act)",
        description=(
            "Move one draft into state/rules/ with approved: true. This is the "
            "only way a rule becomes eligible to fire."
        ),
    )
    sp.add_argument("rule_id", help="the rule_id to approve")
    sp.add_argument("--state-dir", dest="state_dir", help="override the state/ root")
    sp.add_argument(
        "--world-id",
        dest="world_id",
        default=None,
        metavar="SLUG",
        help="world-scoped store under state/world/<slug>/rules (migrates flat on first I/O)",
    )
    sp.add_argument("--json", action="store_true", help="machine-readable output")
    sp.set_defaults(func=cmd_rule_approve)

    sp = rule_sub.add_parser(
        "list",
        help="show approved rules and pending drafts",
        description="List the rule library, keeping approved and draft rules apart.",
    )
    sp.add_argument("--state-dir", dest="state_dir", help="override the state/ root")
    sp.add_argument(
        "--world-id",
        dest="world_id",
        default=None,
        metavar="SLUG",
        help="world-scoped store under state/world/<slug>/rules (migrates flat on first I/O)",
    )
    sp.add_argument("--json", action="store_true", help="machine-readable output")
    sp.set_defaults(func=cmd_rule_list)
