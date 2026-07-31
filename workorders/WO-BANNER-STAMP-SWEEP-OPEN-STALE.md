# WO-BANNER-STAMP-SWEEP-OPEN-STALE

**Status:** READY · EXECUTE · LOW · docs-only tip-honesty
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/BANNER-STAMP-SWEEP-OPEN-STALE`
**Depends:** `main` ≥ `c4d50dc`

## Goal

Stamp stale **OPEN · EXECUTE** banners whose product already landed on `main`.

## Tip-check table (hub 2026-07-31)

| WO | Tip | PR |
|---|---|---|
| PATH-LEAK-UNSTAGED-HONESTY | `d67cd5f` | #233 |
| PLAYER-HALT-NEVER-AUTO-CLASS | `da94f0e` | #214 |
| STATUS-EXPOSE-REPLAY-ARM | `2680538` | #204 |

Re-verify each tip is an ancestor of `origin/main` before stamping. Skip any that fail.

## Scope

Docs-only Status lines → **DONE · tip · #N**. No product code.

## Accept

1. Listed banners no longer claim OPEN EXECUTE when tip is on main.
2. live-prove **n/a**.

## Refs

#286/#284 stamp pattern · IDLE-KICK READY refill
