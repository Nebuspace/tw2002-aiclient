# WO-PLAY-REFLEX-AFFORDANCE — advertise Play `V` reflex in the calm teach band

**Status:** DONE · origin `fd24246` (#236) · Accept verified 2026-07-30
**Posted / seeded:** 2026-07-30T04:03Z · hub (follow-on #235)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `73c5b1c` (`WO-PLAY-REFLEX-ARM` — `V` wired)  
**Refs:** `cockpit/teachband.py` · `cockpit/reflex_controls.py` · `canon/surfaces/mode-line-and-teach-controls.md`

## Goal

`#235` made Play `V` propose + confirm-arm a reflex proposal, but the calm
control-strip teach band still names A/R/T/L/P only. Max cannot *see* that
reflex automation exists in the client. Add a standing `V)reflex` (or
canon-shaped twin) token next to the existing affordances so the wire is
discoverable without reading a WO.

## Scope

- `cockpit/teachband.py` — extend `TEACH_TOKENS` (or equivalent seam) with a
  reflex token; keep ASCII / no-swap; single source of truth for the label.
- Prefer importing a token constant from `reflex_controls.py` (same pattern as
  `PANIC_TOKEN`) so band spelling and key handler cannot drift.
- Update `tests/test_cockpit_teachband.py` (and any stopbanner/control_seat pins
  that snapshot the calm band) so the new token is asserted present and the
  old A/R/T/L/P tokens remain.
- Optional one-line STATUS/hint elsewhere **only** if teachband alone is
  insufficient — prefer the band.

## Constraints

- Labels only in this slice if the key is already wired (#235). Do **not**
  change `V` arm semantics, adapters, or `reflex_arm`.
- Do not invent a second key. Do not steal A/R/T/L/E/D/F/G/P.
- `#218` `app.py` split still frozen — this WO should not need `app.py`.
- No new deps. No tooling riders. No §A.2 / cycles.

## Accept

1. Calm teach band string includes a `V)…` reflex affordance (exact spelling in
   STATUS) whenever the band is composed.
2. Token spelling lives in one product constant shared with (or imported by)
   the band; mutating that constant goes red in a pin.
3. Existing A/R/T (+ L/P if present) tokens remain; focused teachband pins +
   full suite green.
4. Live prove: `n/a` (chrome label only; no new TWGS send path).

## Proof

```bash
pytest -q tests/test_cockpit_teachband.py tests/test_play_reflex_arm.py
pytest -q tests
```

## Follow-on

- Max sacrificial GO for live `V`→`y` arm diversity prove on #235 tip.
- Repeating/cycle semantics for armed reflex (separate core-mechanics WO).
