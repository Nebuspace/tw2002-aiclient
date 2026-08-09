## WO-BUILD-CHAIN-HUNT-SIBLING-EXHAUST-EXPLORE

**Goal:** Build the Chain-hunt taught explore intent — sibling-exhaust-then-advance with
ancestor-port backtrack — as specified in `canon/strategy/exploration-policy.md` §"Chain-hunt
mechanism (sibling-exhaust + ancestor-port backtrack)" (merged `f7de0adf`, 2026-08-09).

**Depends-on:** `WO-CANON-DRAFT-CHAIN-MAXIMIZING-EXPLORE-STRATEGY` (MERGED, `f7de0adf`) — canon is
final for the mechanism shape. **Numeric defaults are still Pending**
(`canon/DECISIONS.md#PENDING-CHAIN-HUNT-SIBLING-EXHAUST-DEPTH-TURN-CAP`) — do NOT hard-code a
sibling-exhaust depth limit or per-run turn-budget cap. Both must be **required, explicit
caller-supplied config** (CLI flag / cockpit arm-time input) with **no built-in default** — fail
closed (refuse to arm) if either is omitted, exactly like `priority_engine.py`'s existing
fail-closed-on-unknown-input pattern. This is how the build proceeds without blocking on the
Pending ruling.

**Scope:**
- New pure planner function(s) in `tw2002_aiclient/explore.py` (or a sibling module if cleaner —
  operator's call), implementing the 5-step sibling-exhaust rule + ancestor-stack backtrack from
  canon lines 116–147:
  1. Anchor on a confirmed-port sector; its unmapped warp-neighbors are a closed work set.
  2. Visit one unmapped sibling at a time (adjacent hop only — reuse `_adjacent_hop_toward`-style
     resolution from Map-fill, don't reinvent adjacency resolution).
  3. Return to the anchoring port sector after the flyby read (no dock required for
     no-port/port-presence classification).
  4. Classify: no-port closes the branch and resumes the set; a port becomes the new anchor,
     recursing the same rule, with the previous anchor pushed onto an ancestor stack.
  5. Advance the primary focus only once the current anchor's closed set is empty; otherwise
     backtrack to the nearest ancestor port with unexhausted siblings — never fall through to
     Map-fill's `densest_reachable_sector`/`plan_exhausted_recovery` while an ancestor still has
     open siblings (canon lines 140–147). Map-fill's generic recovery is the explicit last resort
     only once the ancestor stack is empty and the (caller-supplied, non-default) turn budget
     isn't yet spent.
- Protocol/CLI wiring: a 4th arm-able explore mode alongside Map-fill / Find-StarDock /
  Find-Formations (`session/protocol.py`, `session/cli.py`, mirroring how those three are already
  wired). CLI surface: something like `tw explore start --mode chain-hunt --exhaust-depth N
  --turn-budget M` (naming is the builder's call) — both flags **required** when `--mode
  chain-hunt` is selected, no defaults.
- Tests: pure-planner unit tests for the 5-step rule (closed-set exhaustion order, no-port branch
  closure, port-found recursion/re-anchor, ancestor-stack backtrack correctness, last-resort
  Map-fill fallback only when the stack is truly empty) + protocol/CLI wiring tests mirroring the
  existing `test_cli_explore_wiring.py` / `test_adapters_explore.py` shape.

**Constraints:** Every existing runtime invariant applies unchanged (human-armed opt-in,
stop-on-unknown every cycle, plan-never-blind-send, locate-never-claim — canon lines 167+). Do not
touch `chains.py` (pure cycle-search stays decoupled per its own docstring) or
`sector_explore.py`'s screen-parsing layer beyond whatever minimal hook is needed to trigger the
new planner. Reuse `known_graph`/`frontier_edges`/adjacency-resolution helpers from `explore.py`
rather than duplicating BFS logic.

**Accept:**
- Sibling-exhaust order, no-port closure, port re-anchor/recursion, and ancestor-stack backtrack
  all match canon's 5-step rule exactly — a reviewer should be able to trace each canon numbered
  step to a specific function/branch.
- Chain-hunt never substitutes Map-fill's densest-reachable recovery while an ancestor port still
  has open siblings (this is the one behavior most likely to regress silently into "just Map-fill
  again" — test it explicitly).
- `--exhaust-depth` / `--turn-budget` (or equivalent) are both required with no default; omitting
  either fails closed with a clear error, never a silent fallback number.
- New tests pass; full existing suite has zero regressions.

**Proof:** `pytest` output for the new test file(s) + full suite run; paste the CLI help text
showing both flags as required (no `[default: ...]` on either).

**Sub-parts (independent, dispatch as a build-wave):**
1. Pure planner (`explore.py` additions) + its unit tests — the core algorithm.
2. Protocol/CLI wiring + wiring tests — depends on (1)'s function signatures being stable first,
   so sequence this second within the wave rather than fully parallel.
3. Update `canon/strategy/exploration-policy.md`'s "Code divergence" section is NOT needed here
   (there's no divergence — this WO is building canon into existence, not fixing a mismatch); skip.
