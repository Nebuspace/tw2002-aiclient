# WO-ANET-GAME-SELECT-LETTER-STEP12

**Status:** FIX READY · Cursor latch tighten · hub pytest/push/live-prove · PR #23  
**Posted:** 2026-07-26 · hub live after classify fix: a-net reaches `game_select` then stuck @ ensure step 12  
**Depends:** `25ac393`+ (`WO-ANET-STEP5-LIVE-BYTES` on main)  
**Artifact:** `audit/anet-game-select-letter-step12-20260726.md`

## Goal

After live a-net classifies as `game_select`, `ensure` still fails `automaton_stuck:classification='game_select':step=12`. Send profile `game_letter` (or honest fix) so ensure advances toward `main_command`. **No invent `screen_class`.**

## Evidence

Hub @ tip with chrome-footer classify fix: `proof_anet` ensure → FAIL `game_select`@step=12 (was `menu`@5 before #22).

## Accept

1. Live a-net NEW and/or RETURNING past `game_select` (prefer `main_command`, else next honest class with capture).
2. Pins if product change.
3. STATUS + hub live-prove.

## Out

blank-reject · README · invent class · xeno Phase-2
