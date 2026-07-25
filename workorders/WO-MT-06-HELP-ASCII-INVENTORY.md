# WO-MT-06-HELP-ASCII-INVENTORY

**Status:** DONE (tip pending Accept/land)  
**Goal:** Collecting pin — argparse help/epilog reachable from `build_parser()` stays ASCII-clean for *new* offenders; bank current non-ASCII for Max/MT-05 (no silent scrub).

## Changes
- `tests/test_cli_help_ascii_inventory.py` — inventory walk + known-offender allowlist + `format_help` ★ hole pin

## Banked offenders (tip `d338409`)
- `do`/`send` `--secret` help: em-dash
- `watch` `--compact` help: em-dash
- `menumap` `--world_id` help: ellipsis `…`
- `format_help()` still carries ★ (menumap) → ascii encode fails

## Accept
Suite green with allowlist; **new** non-ASCII help fails. Product scrub waits Max glyph ruling (MT-05).
