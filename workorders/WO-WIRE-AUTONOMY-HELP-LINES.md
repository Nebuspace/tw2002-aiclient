# WO-WIRE-AUTONOMY-HELP-LINES

**Status:** READY · EXECUTE · MED · unused-code WIRE (IDLE-KICK refill)
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/WIRE-AUTONOMY-HELP-LINES`
**Depends:** `main` ≥ `1bcd3c8` (#282 teachband tokens + `compose_autonomy_help_lines`)

## Why

#282 shipped `cockpit/autonomy_keys.compose_autonomy_help_lines()` and the
E/H/O/L one-liners, but the only callers are pins. Unused-code tick marks
`EXPLORE_HELP` / `HOLD_HELP` / `OFFER_HELP` / `CHAINS_HELP` /
`compose_autonomy_help_lines` as **WIRE**. Teachband keeps short TOKENs
(width budget); the honest one-liners need a real product surface.

## Goal

When the Play DECISIONS pane would otherwise be empty (no coach cards, no
explore decision overlay), show the four autonomy help one-liners from
`compose_autonomy_help_lines()` so Ada can discover `E` / `H` / `O` / `L`
without memorizing the band.

## Scope

1. Product call to `autonomy_keys.compose_autonomy_help_lines()` from the
   DECISIONS compose path (preferred: `cockpit/decisions.py` empty-calm
   branch, or the smallest seam that already paints DECISIONS).
2. Clip lines to panel width (reuse existing clip helpers).
3. Do **not** join full HELP lines into the standing teachband (width).
4. Pins: non-test product import/call · empty DECISIONS shows the four
   strings · coach/explore overlays still win when present · confirm-not-auto
   wording preserved on H/O.
5. `workorders/WO-WIRE-AUTONOMY-HELP-LINES.md` on this branch.

## Out of scope

- Silent arm / money-path / daemon changes.
- Putting `EXPLORE_TOKEN` on the teachband (intentional exclusion — FP).
- #283 live diversity (Max GO).
- `#218` app.py split.

## Constraints

- Display-only · no new deps · lead-seat OK · no silent arm.

## Accept

1. Empty calm DECISIONS includes all four `compose_autonomy_help_lines()` strings.
2. Non-empty coach or explore DECISIONS overlay is unchanged (regression pin).
3. Suite green · live-prove **n/a** (copy/chrome).

## Proof

```bash
.venv/bin/python -m pytest tests/test_cockpit_teachband.py tests/test_cockpit_decisions.py -n0
# + new/extended pin for empty-DECISIONS help lines
```

## Disposition

Closes unused-code WIRE for `compose_autonomy_help_lines` + HELP constants
(except `EXPLORE_TOKEN` → FP intentional teachband exclusion; `LIVE_MARKER`
→ FP same-module armconfirm use — hub stamped separately).

## Refs

- #282 · `.samantha/plans/full-autonomy-early-game.md` · unused-code tick 2026-07-31T13:11Z
