# WO-CANON-DRAFT-ARCHIVED-AUTOPILOT-FIVE-DOC-SWEEP

**Status:** DONE · tip-close · PR #448 (`adaa0ac`) · 2026-08-06 re-verify
**Priority:** HIGH
**Gated:** no
**Folded:** `WO-CANON-DRAFT-AUTOHAGGLE-ARCHIVED-AUTOPILOT-NOTE`

**Tip-close (Cycle-43 queue re-flag):** all five named docs + auto-haggle already carry
archive-only / do-not-revive wording on tip; `rg -l 'import autopilot|autopilot.select'
tw2002_aiclient --glob '*.py'` → empty. No further canon edit required.

## Goal

Retag five canon Code-divergence bullets (plus auto-haggle's sibling note) that still describe
pre-rebirth `twclient/autopilot.py`'s per-cycle EV picker as if it were live tip code. Mark each
**archived / do-not-revive** so implementers do not "fix" against dead modules.

## Scope

- `canon/engine/priority-engine.md`
- `canon/engine/coaching-engine.md`
- `canon/strategy/port-economics.md`
- `canon/strategy/ship-progression.md`
- `canon/strategy/exploration-policy.md`
- `canon/engine/auto-haggle.md` (fold-in)
- This WO file

## Accept

1. Each named doc's autopilot EV-select / never-idle bullets say archive-only + do-not-revive (or
   equivalent), matching the pattern already correct in `coverage-metrics.md` /
   `app-autopilot-model.md`.
2. Tip `trade_driver` / ADR-003 / remaining real tip gaps stay distinguishable from archive flags.
3. live-prove: n/a (docs-only).

## Proof

Docs-only; `grep -rl 'import autopilot\|autopilot.select' tw2002_aiclient` stays empty on tip.
