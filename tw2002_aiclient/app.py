"""tw2002-aiclient product entry — curses app router."""

from __future__ import annotations

import argparse
import curses
import sys

from .screens import run_launcher, run_play

_PROG = "tw2002-aiclient"
_DESCRIPTION = (
    "tw2002-aiclient — product TUI (profile launcher, play, Autopilot). "
    "Backend/ops CLI remains ./tw (e.g. ./tw spectate, ./tw status, ./tw ensure)."
)


def _loop(stdscr):
    curses.curs_set(0)
    try:
        curses.use_default_colors()
    except curses.error:
        pass
    while True:
        action, profile = run_launcher(stdscr)
        if action == "quit":
            return 0
        if action == "play" and profile:
            run_play(stdscr, profile)


def run():
    if not sys.stdout.isatty():
        print(
            "ERROR: tw2002-aiclient needs a real terminal (TTY).",
            file=sys.stderr,
        )
        return 2
    return curses.wrapper(_loop)


def main(argv=None):
    parser = argparse.ArgumentParser(prog=_PROG, description=_DESCRIPTION)
    parser.parse_args(argv)
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
