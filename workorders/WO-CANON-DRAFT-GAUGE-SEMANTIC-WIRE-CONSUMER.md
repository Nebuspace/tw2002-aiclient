# WO-CANON-DRAFT-GAUGE-SEMANTIC-WIRE-CONSUMER

**Status:** in flight (impl-aiclient-cursor)  
**Priority:** LOW (Cycle-48 unused-code tick · WIRE-or-park)  
**Depends-on:** none (full visual wire blocked on `turns_max` + HUD motion follow-on)

## Goal

Resolve the unused-code tick on `gauge_semantic`: wire a real fill-fraction
consumer **or** park as intentional scaffolding with honest docstrings.
Verify-first chose **park** — see Evidence.

## Evidence (verify-first, tip `b90755c`)

1. `rg turns_max` across `tw2002_aiclient/` → **zero hits**. Archive
   `_turns_cell` only calls `gauge_semantic` once `tracked["_turns_max"]` is
   known; that accumulator was never ported.
2. `cockpit/hud.py` module docstring (scope boundary §3) explicitly banks
   "turns fuel-gauge" / motion extras as **out of scope** for the freshness
   composer — API is `(value, age_s) -> (text, stale)` only.
3. Play HUD draw (`screens.py` ~1861) dims on `stale` only — no per-cell
   semantic tone path for a gauge color.
4. PWO-040 live note already banked: "NO gauge surface (`gauge_semantic`
   classifier-only; HUD fuel-gauge = banked HUD-extension follow-on)".

Inventing a no-op caller or a bar with no max would be costume, not WIRE.

## Scope

- `tw2002_aiclient/cockpit/tones.py` — park language on `gauge_semantic`
- `tw2002_aiclient/screens.py` — PlayScreen docstring matches park
- this WO file

## Accept

1. Docstrings state **intentional scaffolding** pending a turns-max /
   fuel-gauge follow-on — not "incomplete / ships classifier-only yet".
2. No fake product caller; `gauge_semantic` remains test-covered in
   `tests/test_cockpit_tones.py`.
3. WO records the park rationale + tip evidence above.

## Proof

```bash
.venv/bin/python -m pytest tests/test_cockpit_tones.py -q -n0
rg -n "intentional scaffolding|gauge_semantic" tw2002_aiclient/cockpit/tones.py tw2002_aiclient/screens.py
```

Live-prove: **n/a** (docstring/park honesty only; no session/login/play path).
