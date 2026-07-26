# WO-TUI-HELP-ARGV

**Status:** OPEN · READY · product fix (banked from README discovery)  
**Posted:** 2026-07-26

## Goal

`./tw2002-aiclient --help` / `-h` must print usage and exit 0 without launching curses TUI. Bare `./tw2002-aiclient` still launches TUI.

## Accept

1. `--help` / `-h` → usage, no curses paint, exit 0
2. Bare invoke still TUI
3. Pin (subprocess/pty) proves help does not enter `curses.wrapper`
4. README consistent

## Out

ensure matrix · explore · login automaton
