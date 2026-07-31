# WO-COACH-HAS-PORT

**Status:** DONE · origin `fc39277` (#259) · tip-honesty stamp 2026-07-31 (product on main; banner was stale READY/OPEN)
**Depends:** `main` ≥ `c49819b` (#258)

## Goal

Wire coaching's `has_port` input from an honest off-draw-path producer so the
authored trade-eval card (`docked_at_port`) can fire when the current sector is
known to have a port — not only on rare `cim_report` classifications. Teaching
only; never act.

## Canon

`canon/engine/coaching-engine.md` Code divergence: consumer passes only
classification / fighters / chain / (now) loop_depleting; `has_port` has no
producer on status. Trigger map: "a port in the sector, or a `port_trade` /
`cim_report` classification → `docked_at_port`". Research P-PORT-MASK: docked
port *display* classifies as `main_command`, so classification alone under-fires
the trade card.

## Scope

- Off-draw-path cache (prefer extending `WorldStats` or a tiny sibling — match
  existing refresh cadence: chains popup / explore terminal / live_refresh).
  Lookup: current sector from `status["hud"]["sector"]["value"]` when a real
  int; world-model port presence for that sector.
- Merge `has_port: true` onto the Play status snapshot when observed True;
  **omit** when unknown (do not emit False as confirmed-negative unless a
  completed lookup proved no port for that sector — prefer omit-until-known).
- `cockpit/decisions.py`: pass `has_port=` into `infer_coach_triggers` only when
  the status key is a real bool True (identity-true / fail-closed like
  `loop_depleting`).
- Focused pins + offline suite.

## Constraints

- No draw-path `world_model` / `chain_search` import.
- No daemon status schema change required (client merge OK).
- Never add/request `prompt` on status.
- No send / arm / rotation / run/ touch.
- Card prose stays in `data/coach/strategies.json`.
- Task usage exhausted this session: lead-seat direct build, no subagents.

## Accept

1. Observed port in current sector → status merge carries `has_port=True` and
   idle DECISIONS can surface the authored trade card.
2. Unknown / missing sector / no observation → key omitted; coach stays silent
   for this arm.
3. Hostile / malformed hud sector never raises; never invents True.
4. Draw-path import pin holds.
5. Focused tests + full offline suite green.
6. live-prove: `n/a` — read-only composer/cache wiring.

## Proof

```bash
pytest -q tests/test_coach_engine.py tests/test_cockpit_decisions.py tests/test_world_stats.py
# plus any new pin module for the has_port cache
pytest -q -m "not live_login and not pty_ui"
```

## Refs

- `canon/engine/coaching-engine.md` I2 + Code divergence
- `canon/research/tw2002-screen-patterns.md` P-PORT-MASK
- `world_stats.py` / `chain_status.py` budget pattern
- Plan: Nebuspace `.samantha/plans/coach-has-port-2026-07-30.md`
