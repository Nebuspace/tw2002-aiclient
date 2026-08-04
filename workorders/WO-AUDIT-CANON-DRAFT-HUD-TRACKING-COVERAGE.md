# WO-AUDIT-CANON-DRAFT-HUD-TRACKING-COVERAGE

**Status:** DONE (pending merge) · `impl-aiclient-cursor`
**Priority:** MED
**Depends-on:** none
**Gated:** no — canon fold-in only

## Goal

Give `session/hud_tracking.py` a canon home: sticky cargo extract + the deliberate
never-guess-from-market honesty contract.

## Approach

Fold into existing [trainer-cockpit](../canon/surfaces/trainer-cockpit.md) HUD section
(already documents freshness / seed / cargo at a high level) — name the module, types,
session sticky callers, and silence≠denial cross-link to world-model landmarks.

## Scope

- `canon/surfaces/trainer-cockpit.md` — cargo semantics + citations
- This WO file

## Accept

1. Canon names `hud_tracking.py` / `CargoRead` / sticky session callers.
2. Explicit never-from-market / `observe_holdings` non-write contract.
3. Cross-link to world-model landmark silence rule.
4. live-prove: `n/a` (docs-only).

## Proof

`rg hud_tracking|read_empty_cargo_holds canon/surfaces/trainer-cockpit.md` + STATUS SHA.

## Refs

- queue-aiclient.md `AUDIT-CANON-DRAFT-HUD-TRACKING-COVERAGE`
- `tw2002_aiclient/session/hud_tracking.py`
- `tw2002_aiclient/session/session.py` (`observe_cargo` …)
