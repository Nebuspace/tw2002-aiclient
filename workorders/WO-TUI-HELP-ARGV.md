# WO-TUI-HELP-ARGV

**Status:** OPEN · READY · banked from README rewrite discovery (CC 2026-07-26T19:07:40Z)  
**Posted:** 2026-07-26 · `./tw2002-aiclient --help` silently launches curses TUI

## Goal

`app.py:main()` ignores argv and always `curses.wrapper(_run)`. Fix so `--help` / `-h` print usage (or document no flags honestly without claiming `--help` works). Prefer real argparse `--help` that exits 0 without painting TUI.

## Accept

1. `./tw2002-aiclient --help` prints usage, no curses paint, exit 0.
2. Bare `./tw2002-aiclient` still launches TUI.
3. Pin (pty or subprocess) proves `--help` does not enter wrapper.
4. README stays consistent.

## Out

blank-reject · classify · ensure matrix
