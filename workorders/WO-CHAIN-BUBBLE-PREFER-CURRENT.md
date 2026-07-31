# WO-CHAIN-BUBBLE-PREFER-CURRENT

**Goal:** The always-on Trade Loop Chain strip should prefer a priced
profit cycle that **includes the player's current sector** when one
exists among discovered chains — not always the globally longest cycle
somewhere else on the map.

## Why (Max 2026-07-31)

After #271, priced multi-hop chains surface (good). Ranking is still
`rank_chains` = hop-count desc, then cr/turn — so `chains[0]` / 
`best_chain` can be a 9-hop loop far from where the player is standing.
Max's gut check: “I just passed three ports in a row” — the strip should
feel local when a local cycle exists.

`compose_chain_bubbles` already stars `current_sector` when it appears on
the painted subject; selection never prefers local first.

## Fix

In `tw2002_aiclient/chain_status.py` (pins in
`tests/test_chain_status_coach_wire.py`):

1. On non-empty priced `update`, choose `best_chain` as:
   - among `discovered.chains`, the first chain (already ranked) whose
     `sectors` contain `current_sector` when a current sector is known, else
   - `chains[0]` (unchanged global longest).
2. Current sector source: optional `current_sector=` on `update` /
   `bubble_subject` / a setter the paint path already has — **smallest
   change**: pass `current_sector` into `bubble_subject(current_sector=…)`
   and select at **read** time from retained full ranked list, **or**
   retain `chains` tuple and select in `bubble_subject`. Prefer retaining
   the ranked tuple (or enough of it) so sector changes mid-session
   re-pick without waiting for the next chain tick.
3. Do **not** change `chains.rank_chains` global order (L)chains modal /
   GOALS hop count may keep using longest — only the **bubble strip**
   selection changes. Document that split in the WO STATUS if GOALS still
   shows global hops.
4. If no chain contains current sector → keep today's `chains[0]`.
5. Class-pair fallback unchanged (#269 / #272).

## Accept

1. Unit: two priced chains (long remote + shorter including sector S);
   with `current_sector=S`, `bubble_subject` returns the shorter local one.
2. Unit: same data with `current_sector` absent / not on any chain →
   subject is still the globally first / longest.
3. Unit: class-pair path unchanged (caption rules from #272 still hold).
4. `pytest tests/test_chain_status_coach_wire.py` green (touched pins).

## Scope

- `tw2002_aiclient/chain_status.py`
- Call site(s) that invoke `bubble_subject` / `update` needing current
  sector (likely `screens.py` — already has `cur_sector` for compose)
- `tests/test_chain_status_coach_wire.py`
- `workorders/WO-CHAIN-BUBBLE-PREFER-CURRENT.md`

## Out of bounds

- No change to DFS / trade_adapter / pair detect.
- No “path I walked” history chain invent (only closed ProfitChains).
- No bubble layout redesign.

## Proof

- Offline pins above.
- live-prove **n/a** (selection policy; no live arm). Optional hub store
  probe: with academy world + a known sector on a short cycle, subject
  sectors include that sector when passed as current.

## Refs

- Max report: three ports in a row → two-bubble / far loop
- #271 `WO-CHAIN-SEARCH-SKIP-ZERO-IN` · #272 truncation caption
