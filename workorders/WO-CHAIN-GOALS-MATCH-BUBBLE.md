# WO-CHAIN-GOALS-MATCH-BUBBLE

**Goal:** Align the Play GOALS “Chain N hops” scalar with the always-on
Trade Loop bubble selection — both should prefer a priced cycle through
`current_sector` when one exists (same policy as #273).

## Why

#273 made the bubble strip local-preferring but deliberately left GOALS
on global `best_chain` / `chains[0]`. That split is now confusing: the
strip can show a 3-hop local loop while GOALS still advertises a 9-hop
far cycle. Max’s “I just passed ports here” expectation applies to both
surfaces.

## Fix

Smallest change in `tw2002_aiclient/chain_status.py` (+ pins / call sites):

1. When computing hop scalars for GOALS / coach (`hops` / `unit` from
   `merge` or the hop-count path), use the same selection as
   `_bubble_priced_chain(current_sector)` — local cycle if any, else
   global first.
2. Pass `current_sector` into that path from Play (HUD already has it;
   screens already pass it to `bubble_subject`).
3. Keep `_best_chain` as global longest **only if** some other consumer
   still needs it; otherwise document one accessor:
   `display_chain(current_sector=)` shared by GOALS + bubbles.
4. Do not change DFS / `rank_chains` / pair fallback / truncation caption.

## Accept

1. Unit: long remote + shorter local (includes S); with `current_sector=S`,
   hop scalar and `bubble_subject` both describe the local chain’s hop
   count.
2. Unit: no local chain → both still use global longest.
3. `pytest tests/test_chain_status_coach_wire.py` green (new + existing).

## Scope

- `tw2002_aiclient/chain_status.py`
- Call sites feeding GOALS hop display (likely `screens.py` /
  `merge` / coach wire — tip-check and name in STATUS)
- `tests/test_chain_status_coach_wire.py`
- `workorders/WO-CHAIN-GOALS-MATCH-BUBBLE.md`

## Out of bounds

- No layout redesign
- No walked-path invent
- No change to L)chains modal ranking unless it already reads the same
  scalar (if it does, matching is fine)

## Proof

- Offline pins above
- live-prove **n/a** (selection policy; no live arm)

## Refs

- #273 `WO-CHAIN-BUBBLE-PREFER-CURRENT`
- #271 / #272 bubble honesty chain
