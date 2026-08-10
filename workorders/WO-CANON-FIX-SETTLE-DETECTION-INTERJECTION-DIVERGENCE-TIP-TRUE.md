# WO-CANON-FIX-SETTLE-DETECTION-INTERJECTION-DIVERGENCE-TIP-TRUE

**Status:** DONE (this PR)
**Priority:** LOW (docs honesty residual)
**Source:** residual of DONE `WO-FIX-SETTLE-DETECTION-INTERJECTION-REGISTRY` (#606) /
`WO-CLEANUP-SETTLE-PROFILES-CALLER-MIGRATE` (#653); Aug-09 READY batch otherwise tip-closed

## Goal

Tip-stamp `canon/architecture/settle-detection.md` Code Divergence (1) so it no longer
claims "callers migrating" when tip login already owns the registry path and no product
driver still inlines the nuisance dismiss patterns.

## Verify-first (origin/main `5d5bf691`)

1. `session/login.py` imports and calls `match_interjection` (nuisance branch).
2. Regex pins live only in `session/interjection_registry.py` (login comment: no longer
   re-exports).
3. Product `rg` for `SHOW_LOG_RE|INACTIVITY_RE|BEEN_ON_TODAY_RE|CLEAR_AVOIDS_RE|match_interjection`
   → registry definition + login caller only (tests may import pins).
4. Divergence (1) header still said "LIVE substrate; callers migrating" — tip-false.

## Scope

- `canon/architecture/settle-detection.md` — Divergence (1) tip-stamp
- this WO file

## Out of scope

Behavior change; extending absorption into `watch.py` (by-design stream); new interjection IDs.

## Accept

1. Divergence (1) states login LIVE on `match_interjection`; no "callers migrating" claim.
2. Notes `watch.py` no-auto-handling as by-design, not a migrate gap.
3. Docs-only; no product code change.

## Proof

```bash
rg -n "callers migrating" canon/architecture/settle-detection.md   # expect 0
rg -n "match_interjection" tw2002_aiclient/session/login.py
```

Live-prove: **n/a** (docs-only; no login/play/session arm).
