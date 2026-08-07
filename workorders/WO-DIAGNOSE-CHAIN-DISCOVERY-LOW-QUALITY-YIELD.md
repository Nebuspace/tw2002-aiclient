# WO-DIAGNOSE-CHAIN-DISCOVERY-LOW-QUALITY-YIELD

**Goal:** Explain why `tw chains --world-id scout_academy --json` surfaces
~1.0 `cr_per_turn` loops (26cr / 26 turns) and whether that blocks
credit-doubling because of **missing better candidates** vs **thin map /
ranking surface**.

**Verdict (2026-08-07):** Both — ranking surface hides better yields;
world is also genuinely thin. Not a silent finder bug that fails to
discover profitable edges that exist in the known graph.

## Evidence (recomputed on tip against `state/world/scout_academy`)

| Fact | Value |
|---|---|
| Known sectors | 30 |
| Trade hops | 180 (adapter_note=None) |
| Chains returned | 6378 |
| Search | **partial** — `search_note`: budget 100000 exhausted; 5/23 starts fully searched |
| Hop margins in graph | only `{2.0, 3.0, 4.0}` (unit price deltas) |
| `cr_per_turn` range among found | **0.36 … 3.5** (not all 1.0) |
| Top of `rank_chains` / CLI | long 9-hop cycles at **1.0** (hop-count desc first) |
| Best by yield alone | **2-hop @ 3.5** (sectors 6583↔27958, Organics+Equipment, profit 7 / turns 2) |

Ranking is canon-correct (`canon/strategy/trade-loops.md` § Ranking —
hop-count first, then cr/turn). CLI/JSON inherits that order, so an
operator (or live-drive glance) sees a wall of 1.0 cr/turn long loops and
misses the short higher-yield pairs already in the same payload.

## Root causes (ordered)

1. **Surface / priority ranking vs earn goal** — credit-doubling wants
   credits-per-turn; discovery ranking prefers longer multi-leg loops.
   Same finder; different sort key for the earn surface.
2. **Thin early map** — 30 sectors, tiny unit margins (2–4). Even the
   best known loop is 3.5 cr/turn *before* hold scaling; doubling ~98k
   credits still needs far more map density / richer ports / holds.
3. **Partial DFS** — truncation means absence of still-better cycles is
   **not** established; but better-than-1.0 cycles are already present,
   so truncation is not what created the 1.0 illusion.

## Not the bug

- Finder is not “stuck at 1.0 only.”
- Adapter is not returning empty/truncated hops on this world
  (`adapter_note=None`).

## Recommended follow-ons (do not ship in this diagnose)

1. **Earn-surface ranking** — for credit-doubling / priority earn offers,
   sort (or dual-list) by `cr_per_turn` desc; keep hop-count ranking for
   explore/discovery surfaces. Likely a DECISION if it conflicts with
   hop-count-first canon for the *same* surface.
2. **Map denser / dock more ports** on academy (or pick a richer world)
   before treating chain quality as the credit-doubling blocker.
3. Optional: hold-scaled EV display so unit margins are not mistaken for
   trip P&L.

## Accept (diagnose)

- [x] Recompute chains on `scout_academy` with notes.
- [x] Compare top-ranked vs max-`cr_per_turn`.
- [x] State whether better candidates exist in-graph.
- [x] Name follow-on WOs / DECISION, no silent code change here.

## Refs

queue-aiclient.md · hub live retry 2026-08-07T23:03Z ·
`chains.py:rank_chains` · `chain_search.recompute` ·
`canon/strategy/trade-loops.md`
