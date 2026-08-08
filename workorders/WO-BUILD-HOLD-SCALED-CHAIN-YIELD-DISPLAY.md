# WO-BUILD-HOLD-SCALED-CHAIN-YIELD-DISPLAY

**Status:** IN FLIGHT · Cursor · `wo/BUILD-HOLD-SCALED-CHAIN-YIELD-DISPLAY`
**Seat:** `impl-aiclient-cursor`
**Depends:** `main` ≥ ranking half (#527 / `rank_chains_by_yield`) · diagnosis
`WO-DIAGNOSE-CHAIN-DISCOVERY-LOW-QUALITY-YIELD` follow-on #3
**Refs:** queue-aiclient.md · `chains.py` unit `cr_per_turn` ·
`chain_search_view.format_profit_chain_lines` · `session/cli.py::cmd_chains`

## Goal

Scale displayed chain yield by live (or operator-supplied) hold count so
**unit** hop margins are not mistaken for **trip** P&L. Ranking stays on
the unit field (#527 already shipped yield-first for `tw chains`).

## Formula

```
cr_per_turn_hold_scaled = cr_per_turn × hold_count
```

`cr_per_turn` remains the finder's per-hold unit rate. Fail-closed when
holds are unknown or non-positive — never invent.

## Scope

1. `chains.hold_scaled_cr_per_turn` + `hold_count_from_status` (pure).
2. `chain_search_view.format_profit_chain_lines(..., hold_count=)` — /t
   cells use scaled EV + `hold-scaled ×N` banner when holds known.
3. Cockpit `compose_chain_lines` + Play draw pass live status holds.
4. `tw chains --holds N` (daemon-free CLI) + JSON
   `cr_per_turn_hold_scaled` / top-level `hold_count`.
5. Pins in `tests/test_chains.py`, `tests/test_chain_search_view.py`,
   `tests/test_cli_chains.py`.
6. This WO file.

## Constraints

- Display-only — do **not** change `rank_chains` / `rank_chains_by_yield`
  keys (still unit `cr_per_turn`).
- Do not invent holds; omit scaling when unknown.
- Explicit-path commits; no secrets; no operator-home paths.

## Accept

1. `hold_scaled_cr_per_turn(3.5, 100) == 350.0`; junk → `None`.
2. Formatter with `hold_count=100` shows scaled /t + banner; without holds
   unchanged unit /t.
3. `tw chains --holds 100 --json` emits scaled field; omit holds →
   `cr_per_turn_hold_scaled: null`.
4. Focused pytest green; live-prove `n/a` (offline display math).

## Proof

```bash
.venv/bin/python -m pytest \
  tests/test_chains.py \
  tests/test_chain_search_view.py \
  tests/test_cli_chains.py \
  -q -n0
```

live-prove: `n/a` — display/CLI offline; no TWGS arm.
