# WO-CHAIN-SEARCH-BUDGET — Search budget for find_profit_chains

**Status:** DONE · branch `wo/CHAIN-SEARCH-BUDGET` (not yet merged -- review pending)  
**Posted:** 2026-07-28T00:15:00Z · HIGH · blocks WO-CHAIN-DETECT-WIRE  
**Seat:** impl-claudecode-aiclient  
**Depends:** WO-CHAIN-DETECT-PORT merged on main (#125 `dc1df22`)  
**Refs:** `tw2002_aiclient/chains.py` · `tw2002_aiclient/trade_adapter.py` · `canon/strategy/trade-loops.md`

## Goal

`find_profit_chains` currently defaults to `max_hops=None`: no depth bound and no
iteration budget. `build_trade_hops` caps its output at `DEFAULT_MAX_HOPS = 500`
edges, but 500 edges over ~23 mutually-compatible sectors is K23 — that cap does
**not** protect the finder. When WIRE composes adapter + finder, the composition
detonates:

- unbranched ring n=999 → `RecursionError` escapes the caller
- complete K9 → 6.43 s for one chain; K8 → 0.67 s

Give `find_profit_chains` (and `longest_profit_chain`) its own search budget — a
default `max_hops` cap and/or an iteration counter — returning a truncation `note`
mirroring the `(result, note)` shape `build_trade_hops` already uses. Budget is a
**safety rail**, not an EV-optimizer: canon's hop-count-desc ranking is preserved;
the budget merely stops unbounded search when the graph is pathological.

## Scope

- `tw2002_aiclient/chains.py` — add default search budget to `find_profit_chains`
  and propagate to `longest_profit_chain`; return `(chains, note)` or accept a
  budget param with a safe default
- `tests/test_chains.py` — pin: large ring/K-graph cases hit the truncation note;
  `RecursionError` cannot escape; small graphs with ≤ budget hops are unaffected;
  budget is safety not EV (hop-count-desc ranking preserved on uncapped inputs)
- `workorders/WO-CHAIN-SEARCH-BUDGET.md` — flip to DONE on STATUS

## Accept

1. `find_profit_chains` (and `longest_profit_chain`) on a large ring (n ≥ 500) or
   complete K-graph (K ≥ 9) terminates in < 1 s and returns a non-None truncation
   note.
2. `RecursionError` cannot escape either function under any graph input.
3. On inputs smaller than the budget, behaviour and ranking are identical to
   pre-change (no regression on existing 13 synthetic-graph cases).
4. Canon hop-count-desc ranking is preserved on uncapped inputs (budget fires only
   when the graph would otherwise exceed it).
5. Suite green; STATUS with SHA + junitxml counts.

**No TUI changes. No WIRE changes. No `trade_adapter.py` changes.**

## Constraints

- Do not change `build_trade_hops` or `TradeAdapterConfig.max_hops` — the adapter's
  cap is a separate concern.
- Do not add a priority EV layer or rank-by-budget logic — budget is safety only.
- Do not invent autonomous trade execution or routing.
- No new external dependencies.

**Banked MEDs — OUT OF SCOPE for this WO (separate bank WOs on this branch):**
- `WO-ADAPTER-FRESHNESS-FUTURE-TS` — `_is_fresh` passes future timestamps
  (negative delta satisfies `<= max_age_s`); fix = clamp delta to `[0, ...]`.
- `WO-ADAPTER-SECTOR-ID-INTEGRAL` — `int(rec["sector_id"])` truncates instead of
  validates; `10.9` → `10` silently clobbers a real sector.
- `WO-ADAPTER-CONFIG-GUARDS-LOW` — `bool` passes numeric guards; `ceiling_multiplier
  < 1.0` accepted at config-construction and inverts the price curve.

## Proof

- `pytest tests/test_chains.py -v` — all cases green; new budget cases present.
- Inline timing assertion or comment for the K9 case.
- `RecursionError` mutation: temporarily set budget below depth → assert the error
  does not escape (caught internally or the graph is truncated).

### DONE — what shipped

`chains.py`: `_search_cycles` replaced the recursive `dfs()` with an iterative explicit-stack
DFS (resumable per-node hop-iterators — no Python call recursion at any point, so
`RecursionError` is structurally unreachable, not just pushed past a bigger constant) bounded by
a new `max_search_steps` param (`DEFAULT_MAX_SEARCH_STEPS = 100_000`, a global frame-visit
counter, not a depth cap — the K-graph blowup this guards is breadth, not depth). One search
routine feeds both entry points: `find_profit_chains` keeps its exact pre-change signature/return
type (`list[ProfitChain]`); the new sibling `find_profit_chains_with_note` returns
`(chains, note)` — same shape as `trade_adapter.build_trade_hops` — as the honest entry point for
WIRE, `note` naming the budget, chains found, and start-sectors fully searched before truncation.
`longest_profit_chain` unchanged (forwards via `**kwargs`, inherits the default budget for free).
No `trade_adapter.py` / TUI / WIRE changes.

`tests/test_chains.py`: 10 new cases (23 total, 13 pre-existing untouched) — differential proof
(300 seeded pseudo-random small graphs, exact-equality against a vendored pre-change recursive
oracle, catches any traversal-order drift the recursion→iteration conversion could have
introduced); ring(500)/K9 truncate <1s with a note (measured ~0.05–0.4s); ring(5000)/ring(50000)
return normally (no `RecursionError`); ring(999) reproduces the exact original crash against the
vendored legacy oracle while the new code handles it fine; a call-stack-depth mutation proof
(shrinks `sys.recursionlimit` to just above pytest's own ambient depth) proves the new search
never touches the Python call stack at all, not merely that today's inputs fit under today's
default limit. Every new pin mutation-proven by literally breaking it and watching the test go
red, then reverting: disabling the `steps > max_search_steps` guard turned K9 from 0.4s→5.6s and
ring(5000) from fast→17.8s (both blew past their `<1s`/`<5s` assertions, confirming the guard is
load-bearing, not decorative); reintroducing real recursion into `find_profit_chains` made the
ring(999)/call-stack tests fail with an actual `RecursionError` (proving those tests really do
detect a recursive regression, not just today's absence of one).

Full suite: `pytest tests/ --junitxml=...` — read from the XML after process exit (not the
captured summary line) — **5270 tests, 0 failures, 0 errors, 3 skipped** (main's baseline was
5260/0/3; the +10 delta is exactly the new chains cases, nothing else moved).
