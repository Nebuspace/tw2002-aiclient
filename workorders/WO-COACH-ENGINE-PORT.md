# WO-COACH-ENGINE-PORT — Rebirth port of coaching-engine kernel

**Status:** OPEN EXECUTE · HIGH · Claude Code preferred  
**Posted:** 2026-07-28T12:28Z · hub (CC DECISION 12:25Z · supersedes premature W5 unbank)  
**Blocks:** `WO-COACH-CHAIN-TRIGGER` (W5) until this lands  
**Refs:** `canon/engine/coaching-engine.md` · pre-rebirth `2a7d03f:twclient/spectate_layout.py` (`infer_coach_triggers`, `compose_decisions_coach`) · rebirth `452d896` deletion

## Goal

Restore the **coaching-engine kernel** at tip: `coach_kb` loader/validator + `infer_coach_triggers` + `compose_decisions_coach`, matching canon's L29–32 / L71 / L92 contracts — without porting full spectate (3000+ lines).

## Scope

- Port or re-extract `coach_kb.py` (load **existing** `data/coach/strategies.json` + `params.json` at tip — **no duplicate card sources**)
- New module(s) under `tw2002_aiclient/` (not `twclient/`)
- Pins + suite coverage for loader + trigger map + compose (un-ignore or new tests as needed)
- Local canon status fix: `canon/engine/coaching-engine.md` "as implemented" prose → honest (staged in-repo; public docs push Max-gated)

## Out of scope

- W5 discovered-chain DECISIONS wire (follow-on WO)
- Full `spectate_layout` / spectate app port
- Inventing card text or a second formatter

## Accept

1. `infer_coach_triggers` and `compose_decisions_coach` callable from product code with fail-closed trigger behavior per canon.
2. `coach_kb` loads tip data files only; schema validation pins.
3. Suite green; STATUS with SHA + dependency note (what was extracted vs spectate).

## Constraints

Public-repo safe. No autonomous arm. Cipher glance on Accept if auth-adjacent surfaces touched.
