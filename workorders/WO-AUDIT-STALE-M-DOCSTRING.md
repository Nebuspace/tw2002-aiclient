# WO-AUDIT-STALE-M-DOCSTRING — Retire stale M=Mode docstring literals

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-25 · tip **`ca1e078`** (CC · Fable 5; stacked same wave as entry-APP `7c0e882`)
> Type: harden/docs · Priority: P1 · Lens: L2 code-vs-canon / stale literal
> Refs: ADR-002 (Ctrl-A replaces printable M for Mode) · `tw2002_aiclient/session/` docstrings

## Goal
Find and retire stale docstring / comment literals that claim `M` = Mode (printable M as Mode key), now that ADR-002 established Ctrl-A as the Mode chord. Stale literals make future auditors assume the wrong key — a canon-honesty issue, not a product regression.

## Scope
- `tw2002_aiclient/` docstrings / comments claiming `M` = Mode (not Move, not the MANUAL badge)
- No product behavior change; docstring-only updates

## Constraints
- Do NOT retire `M` = TW Move (still correct — attached bare M reaches game)
- Do NOT change code logic; docstring-only
- `_MODE_KEY` duplication fix stays in 061-ENTRY; this WO is subsequent honesty sweep

## Accept
1. No surviving docstring/comment that claims printable `M` = Mode toggle
2. `M` = TW Move references preserved
3. Full suite green (no behavior change)

## Proof
grep sweep + docstring-diff; STATUS + SHA (`ca1e078` on origin stacked with entry-APP).

## Refs
ADR-002 · CC STATUS @ 10:12:39Z (stale-M `c6b5616` + 061-ENTRY `35cca4d` pre-push) · final origin `ca1e078`
