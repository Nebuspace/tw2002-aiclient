# WO-EXPLORE-HALT-REASON-CLASS — Carry classify class in explore halt reasons

**Status:** OPEN · EXECUTE · HIGH · diagnosis honesty (post #211/#212)
**Posted:** 2026-07-29T05:23Z · Max carte blanche / automation continuity
**Seat:** impl-claudecode-aiclient (offline) · live → Cursor (optional / n/a OK if offline-only)
**Depends:** #207 fighter_encounter classify on main · #211 dock reason-split precedent
**Refs:** `session/sector_explore.py` `_gate_screen` · live cells that halted `unrecognized_screen` on fighter `Option?` · CC bank 2026-07-29

## Why

Explore `_gate_screen` collapses every non-movement / never-auto class into the halt string **`unrecognized_screen`**, even when `classify` already named the screen (`fighter_encounter`, `money_prompt`, …). Live matrices then look like a missing classifier — the same ambiguity shape that cost the dock WO a full diagnosis cycle (`dock_screen_unrecognized` meaning two different failures).

## Goal

Halt reasons must not lie. When classify knows the class, the explore halt reason must carry that class (or a distinct `halt_screen_not_drivable:<class>` / equivalent), not pretend the screen was unrecognized.

## Accept

1. `_gate_screen` (and any twin sites) report a reason that includes the classify class when known — e.g. `never_auto_action:money_prompt` / `halt_not_drivable:fighter_encounter` — **not** bare `unrecognized_screen` for a recognized class.
2. True unknowns still halt with a typed unknown/unrecognized reason (do not invent classes).
3. Pins: fighter_encounter fixture → reason contains `fighter_encounter` (or agreed vocabulary); money_prompt → contains `money_prompt` / `never_auto`; mutating back to collapse-all-to-unrecognized goes red.
4. No behavior change to *whether* we halt — only the reason string / vocabulary honesty.
5. Suite · STATUS · Live: DEFERRED → Cursor **or** honest `n/a` (offline vocabulary; hub may Accept n/a with reason).

## Constraints

- Do not claim `Your offer` as `money_prompt` (canon collision with auto-haggle).
- Do not implement option-2 (`0` decline).
- Do not grow `app.py` further for this — explore/session lane only.
- Public-safe only.

## Proof

```text
pytest tests/test_explore*.py tests/test_never_auto_action.py -q -n0
# + suite on PR · mutation on collapsed reason
```
