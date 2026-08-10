# WO-BUILD-TURNS-FUEL-GAUGE-MAX-ACCUMULATOR

**Status:** DONE (this PR)
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/BUILD-TURNS-FUEL-GAUGE-MAX-ACCUMULATOR`
**gated:** no · **schema:** n/a · **live-prove:** n/a (offline HUD / session sticky)

## Goal

Land the documented TURNS fuel-gauge: session `turns_max` high-water accumulator
(archive `tracked["_turns_max"]`) plus HUD cell renderer calling
`gauge_semantic(turns_remaining/turns_max)` — first real product caller for
`gauge_semantic`.

## Verify-first (origin/main @ 30ce0a8a)

- `cockpit/tones.py` `gauge_semantic` — park language; zero product callers
  beyond tests (cycle-49 / prior #496 park).
- `cockpit/hud.py` — freshness composer only; docstring banks fuel-gauge as
  deferred; no `turns_max` on tip (`rg turns_max tw2002_aiclient/` → empty).
- Archive `spectate_layout.update_tracked_stats` / `_turns_cell` /
  `render_bar_meter` / `TURNS_GAUGE_WIDTH=10` — canonical port shape.
- Daemon already has `Session.observe_turns` / `turns_snapshot` sticky; HUD
  wire is `status["hud"]["turns"] = {value, age_s}` via `protocol._hud_payload`.

## Scope

- `tw2002_aiclient/session/session.py` — `last_turns_max` accumulator on observe
- `tw2002_aiclient/session/state_parser.py` — optional `TurnsSnapshot.turns_max`
- `tw2002_aiclient/session/protocol.py` — emit `turns_max` on turns HUD cell
- `tw2002_aiclient/cockpit/hud.py` — `render_bar_meter`, TURNS gauge + tone
- `tw2002_aiclient/cockpit/tones.py` — tip-true product-caller docstring
- `tw2002_aiclient/screens.py` — draw gauge tone (+ dim when stale)
- `canon/surfaces/{visual-language,trainer-cockpit}.md` — TARGET→SHIPPED
- tests + this workorder

## Out of scope

- Credit delta-chip / tween / sparkline motion polish
- WO-CANON-FIX-EXPLORATION-POLICY-STALE-4-INTENT-CYCLE (HOLD)
- Max-gated BOUNDED-REPEAT escalate

## Accept

1. Observing rising then falling turns leaves `turns_max` at the session high.
2. `status["hud"]["turns"]` carries `turns_max` when known.
3. `compose_hud_cells` appends `[████░░░░░░]` (ASCII twin when `unicode_ok=False`)
   and returns `gauge_semantic` tone on the TURNS value row.
4. Focused pytest green; sibling monkeypatch fixtures updated for 3-tuple cells.

## Proof

```bash
.venv/bin/python -m pytest \
  tests/test_cockpit_hud.py \
  tests/test_cockpit_tones.py \
  tests/test_hud_status_bridge.py \
  tests/test_cockpit_hud_pty.py -q -n0
```

Live-prove: **n/a** (UI/session sticky only; no login/play money path).
