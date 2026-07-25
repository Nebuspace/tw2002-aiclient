# WO-P2-OPS-VERB-D — tw start (docs-only / deferred; ensure owns spawn)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE (docs-only)** 2026-07-24 · tip **`1d85c41`** (Cursor)
> Type: docs/deferred · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-P2-OPS-VERB-SURFACE.md` slice D

## Goal
Slice D — `tw start` (explicit spawn). Prefer docs-only / honesty if it overlaps `ensure` heavily; only wire a thin explicit-spawn CLI if clearly additive. Outcome: docs-only. `ensure` owns spawn; no parallel `start` protocol verb invented.

## Scope
- README honest note (tw start → `ensure` semantics, no duplicate)
- `WO-P2-OPS-VERB-SURFACE.md` slice-D tick

## Constraints
- No screens/cockpit; no state_parser
- `ensure` owns spawn — do not duplicate or scoop

## Accept
- Docs-only: STATUS cites `ensure` owns spawn; README honest; `./tw --help` unchanged; no fake verb
- Full suite green (if code) or attributed

## Proof
STATUS + SHA disclosing docs-only rationale. Hub Completeness 97 / Quality 96 → SHIP.

## Refs
`WO-P2-OPS-VERB-SURFACE.md` slice D · hub Accept + Push GO @ 13:47:11Z
