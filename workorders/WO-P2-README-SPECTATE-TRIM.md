# WO-P2-README-SPECTATE-TRIM — Remove detailed future tw spectate control-strip subsection from README

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`41bf20a`** (Cursor)
> Type: docs · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-P2-OPS-VERB-SURFACE.md` slice F note

## Goal
Shorten the detailed future `tw spectate` control-strip subsection in README.md to a brief "Coming" pointer. Avoid reading as a shipped feature. Multi-paragraph key table removed; short Coming→slice-F note remains.

## Scope
- `README.md` only (no code, no verb implement)

## Constraints
- Keep one short "Coming" pointer to slice F
- No code changes

## Accept
1. No multi-paragraph `tw spectate` control UI presented as present
2. Short "Coming" pointer to slice F remains

## Proof
Diff: multi-paragraph key table gone · short Coming→slice F. Hub Completeness 96 / Quality 95 → SHIP.

## Refs
hub Accept + Push GO @ 12:34:40Z · banked residual after WO-P2-README-NARRATIVE-HONESTY
