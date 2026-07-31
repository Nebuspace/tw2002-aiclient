# WO-CHAIN-BUBBLE-TRUNCATION-CAPTION

**Goal:** When the always-on Trade Loop Chain strip falls back to a class
pair because the *priced* search did not finish (truncated empty), the
caption must say so — not bare `"class pair"`, which reads as “we looked
and this is the honest answer.”

## Why (Max 2026-07-31 · residual after #271)

`#271` fixed SSS in-degree-0 starts burning the DFS budget so priced
cycles can surface. Residual honesty gap remains:

- `ChainScalars.update`: empty + `truncated` → **not seen** (retain last
  `best_chain`; if none ever found, stay `None`).
- Idle tick still calls `update_pairs` → `bubble_subject` returns
  adapted pair with caption `"class pair"`.
- Operator sees a confident 2-bubble strip while the priced search never
  established absence (`detail`: “absence is not established”).

That costume is what made the pre-#271 bug feel like “the product only
ever finds pairs.”

## Fix

In `tw2002_aiclient/chain_status.py` (and pins in
`tests/test_chain_status_coach_wire.py`):

1. Remember when the latest priced `update` was **truncated-empty**
   (not-seen path that returned early because `truncated`).
2. Clear that flag on any completed priced update (non-empty chains, or
   empty non-truncated / non-no_world_model).
3. `bubble_subject()`: if falling back to pair **and** that flag is set,
   caption = `"class pair · search incomplete"` (exact string — pin it).
   Otherwise keep `"class pair"`.
4. Do **not** invent margin. Do **not** hide the pair (still useful
   chrome). Do **not** change `chains._search_cycles` (already fixed).

## Accept

1. Unit: truncated-empty priced result + non-empty pairs →
   `bubble_subject` caption is `"class pair · search incomplete"`.
2. Unit: completed `no_closed_cycle` (not truncated) + pairs → caption
   remains `"class pair"`.
3. Unit: non-empty priced chains → subject is `best_chain`, caption
   `None` (unchanged).
4. `pytest tests/test_chain_status_coach_wire.py` green.

## Scope

- `tw2002_aiclient/chain_status.py`
- `tests/test_chain_status_coach_wire.py`
- `workorders/WO-CHAIN-BUBBLE-TRUNCATION-CAPTION.md`

## Out of bounds

- No UI layout redesign of bubbles.
- No change to `rank_chains` / prefer-nearby (separate product decision).
- No daemon / status JSON fields for the flag.

## Proof

- Offline pins above.
- live-prove **n/a** (caption honesty; no live arm / money path). Cite
  reason in STATUS.

## Refs

- `#271` / `WO-CHAIN-SEARCH-SKIP-ZERO-IN`
- `#269` / `WO-CHAIN-BUBBLE-PAIR-FALLBACK`
- `chain_search.ProfitChainResult.detail` truncated-empty wording
