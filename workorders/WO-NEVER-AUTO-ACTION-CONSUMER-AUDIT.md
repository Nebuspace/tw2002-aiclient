# WO-NEVER-AUTO-ACTION-CONSUMER-AUDIT

**Status:** DONE · PR #34 · origin `3fa3493`  
**Posted:** 2026-07-26 · from `audit/session-classify-audit-coverage-20260726.md` C-06  
**Base tip:** `origin/main` (`94a29f4` or newer)

## Goal

Prove every send path that keys off screen classification either whitelists `main_command` or intersects `NEVER_AUTO_ACTION_CLASSES` so `money_prompt` cannot be auto-keyed.

## Scope

- Inventory of classification→send consumers (`menu/crawler.py`, `loops/player.py`, guardian, daemon quit, cockpit taught-rule / arm fire, any other senders found)
- Pins and/or a single inventory assert that fails when a new consumer omits the refuse
- **Out:** Explore HOLD · invent classify vocab · live third-party proves · credentials/auth redesign

## Accept

1. Written inventory (audit note or test docstring) of every sender that uses classification to choose keystrokes.
2. Each sender either (a) intersects `NEVER_AUTO_ACTION_CLASSES` / refuses `money_prompt`, or (b) is documented fail-closed via `main_command`-only whitelist with a pin.
3. At least one regression pin that would fail if a listed consumer dropped the refuse.
4. `pytest` green for touched tests; no live connects.

## Proof

STATUS + SHA · inventory path · pin names · `pytest` excerpt.

## Refs

`audit/session-classify-audit-coverage-20260726.md` C-06 · `NEVER_AUTO_ACTION_CLASSES` in `session/classify.py`
