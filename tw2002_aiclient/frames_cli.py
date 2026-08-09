"""``tw frames {tail,show,grep,diff}`` — settle-frame post-mortem CLI.

Filesystem-only over ``state/frames/*.jsonl``. Never opens a daemon socket,
never sends. Lives outside ``session/cli.py`` for the same line-cap reason
as ``mine_cli`` / ``skill_cli``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from tw2002_aiclient import frame_recorder as fr

__all__ = ["add_frames_parsers", "cmd_frames"]


def cmd_frames(args: argparse.Namespace) -> int:
    """Read-only post-mortem over ``state/frames/*.jsonl``."""
    action = getattr(args, "frames_action", None) or "tail"
    session = getattr(args, "session", "latest") or "latest"
    state_dir = getattr(args, "state_dir", None)
    if state_dir is not None:
        state_dir = Path(state_dir)

    if action == "tail":
        frames = fr.read_frames(session, state_dir=state_dir)
        n = getattr(args, "n", 20) or 20
        frames = frames[-n:]
        if getattr(args, "json", False):
            print(json.dumps({"ok": True, "frames": frames, "count": len(frames)}))
            return 0
        if not frames:
            print("(no frames -- daemon not recording yet, or wrong --session)")
            return 0
        for f in frames:
            print(
                f"#{f.get('seq')} {f.get('ts')} {f.get('classification')} "
                f"prompt={f.get('prompt')!r} sent={f.get('sent_input')!r}"
            )
        return 0

    if action == "show":
        frames = fr.read_frames(session, state_dir=state_dir)
        seq = int(args.seq)
        match = next((f for f in frames if f.get("seq") == seq), None)
        if match is None:
            print(f"seq {seq} not found", file=sys.stderr)
            return 1
        if getattr(args, "json", False):
            print(json.dumps({"ok": True, "frame": match}))
            return 0
        raw = match.get("screen_raw") or []
        print(
            f"# seq={match.get('seq')} ts={match.get('ts')} "
            f"class={match.get('classification')}"
        )
        print(f"# prompt={match.get('prompt')!r} sent={match.get('sent_input')!r}")
        for line in raw:
            print(line)
        return 0

    if action == "grep":
        hits = fr.grep_frames(args.pattern, session, state_dir=state_dir)
        if getattr(args, "json", False):
            print(json.dumps({"ok": True, "hits": hits, "count": len(hits)}))
            return 0
        if not hits:
            print("(no matches)")
            return 0
        cre = re.compile(args.pattern)
        for f in hits:
            print(
                f"#{f.get('seq')} {f.get('ts')} {f.get('classification')} "
                f"prompt={f.get('prompt')!r}"
            )
            for line in f.get("screen_raw") or []:
                if cre.search(line):
                    print(f"  | {line}")
        return 0

    if action == "diff":
        frames = fr.read_frames(session, state_dir=state_dir)
        by_seq = {f.get("seq"): f for f in frames}
        a = by_seq.get(int(args.seq_a))
        b = by_seq.get(int(args.seq_b))
        if a is None or b is None:
            print("seq not found", file=sys.stderr)
            return 1
        delta = fr.diff_frames(a, b)
        if getattr(args, "json", False):
            print(json.dumps({"ok": True, "diff": delta, "count": len(delta)}))
            return 0
        if not delta:
            print("(identical screen_raw)")
            return 0
        for line in delta:
            print(line)
        return 0

    print(f"unknown frames action: {action}", file=sys.stderr)
    return 2


def add_frames_parsers(sub: argparse._SubParsersAction) -> None:
    """Register ``tw frames {tail,show,grep,diff}``."""
    frames_p = sub.add_parser(
        "frames",
        help=(
            "post-mortem full 80x25 settle frames under state/frames/ "
            "(tail/show/grep/diff; no daemon required)"
        ),
    )
    frames_sub = frames_p.add_subparsers(dest="frames_action", required=True)

    def _state_dir(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--state-dir",
            default=None,
            dest="state_dir",
            metavar="PATH",
            help="state root override (default: project state/)",
        )

    ft = frames_sub.add_parser("tail", help="last N frames (metadata)")
    ft.add_argument("--session", default="latest", help="session id or 'latest' (default)")
    ft.add_argument("-n", type=int, default=20, help="how many frames (default 20)")
    ft.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    _state_dir(ft)
    ft.set_defaults(func=cmd_frames)

    fs = frames_sub.add_parser("show", help="print one frame's screen_raw")
    fs.add_argument("seq", type=int, help="frame sequence number")
    fs.add_argument("--session", default="latest")
    fs.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    _state_dir(fs)
    fs.set_defaults(func=cmd_frames)

    fg = frames_sub.add_parser(
        "grep", help="frames matching pattern in prompt/screen_raw"
    )
    fg.add_argument("pattern", help="substring/regex matched against prompt + screen_raw")
    fg.add_argument("--session", default="latest")
    fg.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    _state_dir(fg)
    fg.set_defaults(func=cmd_frames)

    fd = frames_sub.add_parser("diff", help="line delta between two frame seqs")
    fd.add_argument("seq_a", type=int)
    fd.add_argument("seq_b", type=int)
    fd.add_argument("--session", default="latest")
    fd.add_argument("--json", action="store_true", help="machine-parseable JSON output")
    _state_dir(fd)
    fd.set_defaults(func=cmd_frames)
