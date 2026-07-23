"""tw2002-aiclient product entry — curses app router."""

from __future__ import annotations

import curses
import sys

from .screens import run_launcher, run_play


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
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
