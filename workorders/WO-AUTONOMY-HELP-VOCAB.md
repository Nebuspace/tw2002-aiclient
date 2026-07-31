# WO-AUTONOMY-HELP-VOCAB

**Status:** READY · EXECUTE · HIGH · Play-visible · Cursor  
**Seat:** `impl-aiclient-cursor`  
**Branch:** `wo/AUTONOMY-HELP-VOCAB`  
**Depends:** `main` ≥ `183ac8e` (strip policy + trade backoff)

## Why

`cockpit/autonomy_keys.py` still teaches the **pre-ruling** trainer model via `compose_autonomy_help_lines()` (drawn into decisions/help):

- `EXPLORE_HELP` = “start explore via **confirm gate**” — Max: App-armed `E` = infinite find-StarDock, no confirm default
- `HOLD_HELP` / `OFFER_HELP` still on the help tuple — Max: Hold?/Offer? **dropped** from calm strip; cargo/ship are **C/S ·ON/OFF** policies; Offer not a key
- `CHAINS_HELP` may still say `L)chains` — calm chrome is **`L)ist Loops`** / **`T)rade Loop Chain`**

Unused-code tick tip-check (2026-07-31): `EXPLORE_HELP` flagged WIRE — product help surface exists (`decisions.py` → `compose_autonomy_help_lines`) but strings are **canon-stale**.

## Goal

Make autonomy **help lines** match the calm teachband + App-armed policy Max ruled 2026-07-31 (same vocabulary as `cockpit/teachband.py` / strip).

## Scope

1. Rewrite `EXPLORE_HELP` / retire or replace `HOLD_HELP`+`OFFER_HELP` in `compose_autonomy_help_lines()` with calm-model lines covering at least: **E** explore (infinite / find StarDock under App), **P/C/S** policy toggles, **T** trade loop chain, **L** list loops, **Mode/^A** App↔Manual (= halt). No confirm-gate / Hold? / Offer? / Panic as primary help.
2. Update pins in `tests/test_cockpit_decisions.py` / `tests/test_cockpit_teachband.py` (and any direct string asserts) so they expect the new vocabulary — not the old confirm/Hold?/Offer? lines.
3. Keep `EXPLORE_TOKEN` / teachband tokens unchanged unless a help string must cite them verbatim.
4. This WO file on the branch.

## Out of scope

#283 live diversity · formations catalog · `compose_explore_offer` retire (bank separately) · `compose_arm_chip` delete · rewriting teachband layout.

## Accept

1. Help lines shown via `compose_autonomy_help_lines` / decisions path match calm strip vocabulary (no confirm-gate / Hold? / Offer? as taught defaults).
2. Focused decisions + teachband + autonomy_keys pins green; full `pytest tests/` green.
3. Live-prove: **n/a** (chrome/help copy only) unless seat touches money-path start verbs.

## Proof

pytest + STATUS. No self-merge.

## Refs

`.samantha/plans/play-strip-autonomy-keys.md` · `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` · `cockpit/autonomy_keys.py` · `cockpit/decisions.py` ~303 · unused-code tick 20260731T2345Z
