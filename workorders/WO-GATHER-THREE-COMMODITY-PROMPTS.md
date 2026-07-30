# WO-GATHER-THREE-COMMODITY-PROMPTS — Decline every new-port commodity prompt

**Status:** OFFLINE COMPLETE · HIGH · money-path · Max-approved 2026-07-30

## Goal

Gather declines each of the possible Fuel Ore, Organics, and Equipment
quantity questions with `0`, then resumes Explore only after the live input
cursor reaches the ship command prompt.

## Constraints

- Gather never trades: only exact commodity quantity prompts may receive `0`.
- At most three declines; a fourth prompt, offer, bank question, unknown
  screen, or missing cursor provenance halts.
- Stale painted `Command` text must not end the cascade.
- No Attack, haggle, blank offer acceptance, schema change, or dependency.

## Accept

- [x] One-, two-, and three-question cascades complete with one `0` each.
- [x] A cumulative three-question grid with stale `Command` text below the
      active question still declines all three.
- [x] The live cursor row, not the last painted row, owns confirmation.
- [x] Existing fourth-question and non-commodity refusal pins remain green.
- [x] Full offline suite passes.

## Proof

```bash
pytest -q -n 0 tests/test_explore_dock_new_port.py tests/test_session.py \
  tests/test_settle.py tests/test_settle_real_screen.py
pytest -q -m "not live_login and not pty_ui"
```
