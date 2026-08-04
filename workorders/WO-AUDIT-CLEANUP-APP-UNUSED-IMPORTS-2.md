# WO-AUDIT-CLEANUP-APP-UNUSED-IMPORTS-2

**Status:** CLAIMED by `impl-aiclient-cursor` (`📋 CLAIM` 2026-08-04T18:12:14Z)
**Priority:** LOW
**Depends-on:** none
**Gated:** no

## Goal

Remove two unused imports in `app.py`: `_analyze` and `_trade_discovery_blocks_start`.

## Scope

- `tw2002_aiclient/app.py`
- This WO file

## Accept

1. Neither symbol remains as an import or reference in `app.py`.
2. Floor imports from `trade_chain` retained (still used).
3. live-prove: `n/a` (import cleanup only).

## Proof

`rg` clean + suite smoke / targeted import. STATUS with SHA.

## Refs

- queue-aiclient.md `AUDIT-CLEANUP-APP-UNUSED-IMPORTS-2`
