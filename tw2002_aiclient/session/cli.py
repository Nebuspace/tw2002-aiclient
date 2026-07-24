"""Minimal ``tw`` CLI stub — empty verb table (WO-P0-004)."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tw",
        description="tw2002-aiclient backend/ops CLI (verb table empty until later WOs).",
    )
    parser.add_argument(
        "verb",
        nargs="?",
        default=None,
        help="CLI verb (none registered yet)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    # No verbs yet — --help handled by argparse (exit 0). Bare invoke: show help.
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
