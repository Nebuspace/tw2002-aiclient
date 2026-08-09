## WO-CANON-DRAFT-CHAIN-MAXIMIZING-EXPLORE-STRATEGY

**Goal:** Draft canon (and, once ratified, build) a sibling-exhaust-then-advance exploration
mode that maximizes confirmed trade-loop chain length, replacing the implicit assumption that
Map-fill's global nearest-first frontier pick is an adequate chain-hunting strategy.

**Origin:** Max, 2026-08-09, walking a concrete example: sector 5 has a port and warps to 6,
7, 8, none visited. Current Map-fill (`explore.py:171-199 pick_frontier_edge`) picks the single
globally-nearest unmapped frontier edge each tick — it does not exhaust 5's own siblings (6, 7,
8) before letting the frontier push on past whichever one it visits first, and there is no
"return to the last sector with a confirmed port" backtrack on a dead end (recovery instead
falls through to `plan_exhausted_recovery` / `densest_reachable_sector`, a generic map-fill
heuristic with no chain-awareness). Re-verified directly against `explore.py:101-199` and
`canon/strategy/exploration-policy.md` before filing this — confirmed the gap is real, not a
misreading: canon's own "BFS / frontier planner mechanism (G1)" section describes exactly the
global-nearest-first-no-sibling-sweep behavior the code implements, so this is a genuine
uncovered strategy, not a code-vs-canon divergence.

**Scope (canon-draft phase — this WO):**
- `canon/strategy/exploration-policy.md` — add a fourth taught intent (working name:
  `Chain-hunt`) alongside Map-fill / Find-StarDock / Find-Formations, specified as:
  - At a sector with a confirmed port, treat its unmapped warp-neighbors as a closed set to
    exhaust before advancing past any of them: visit, read the free flyby line, return to the
    port sector.
  - A neighbor with no port closes that branch (cheap — one round-trip, no dock needed).
  - A neighbor with a port becomes the new chain frontier; recurse the same exhaust-then-advance
    rule from there.
  - A sector fully exhausted with no port triggers backtrack to the nearest ancestor port that
    still has unexhausted neighbors — not the generic map-fill recovery path.
  - Name the explicit tradeoff: ~2x the hop count vs. Map-fill's 1x per neighbor (each sibling
    costs a there-and-back instead of a one-way advance) in exchange for guaranteed maximal
    chain-length discovery in the covered area. This is a real turn-budget cost — canon must
    say so plainly, not bury it.
  - Still subject to every existing runtime invariant: human-armed opt-in, stop-on-unknown every
    cycle, plan-never-blind-send, locate/catalog/recommend-never-claim.
- `canon/strategy/trade-loops.md` — cross-link: note that Chain-hunt is the exploration-side
  counterpart to `chains.py`'s pure cycle-search (`chains.py:1-13` docstring) — Chain-hunt grows
  the map in a chain-length-maximizing shape; `chains.py` still does the actual ranking over
  whatever the world model holds. Chain-hunt does not replace or call into `chains.py`.
- `canon/DECISIONS.md` — file the open numeric question (default sibling-exhaust depth limit /
  turn-budget cap per Chain-hunt run) as Pending for a human ruling before the build phase.

**Explicitly NOT in this WO's scope:** the actual `session/` implementation (new pure planner
function, protocol/CLI wiring, tests) — that is a follow-on build WO once the canon draft is
reviewed, since this is a new strategy shape worth a design pass before code, not a mechanical
fix.

**Constraints:** DOCS-WIN framing — this is net-new canon, not a correction to existing canon
(exploration-policy.md's existing G1 description is accurate to the code as-is). Don't touch
`explore.py` / `sector_explore.py` in this WO. Ungated — no auth/payments/MFA/admin/AI-safety
surface touched.

**Accept:**
- `exploration-policy.md` gains the fourth intent, written at the same prescriptive-spec level
  of detail as the other three, with the sibling-exhaust/backtrack mechanism spelled out
  concretely enough that a follow-on build WO could implement it without re-deriving the design.
- The turn-budget tradeoff is stated in the doc, not left implicit.
- `trade-loops.md` gets the one cross-link paragraph, not a rewrite.
- `DECISIONS.md` carries the Pending numeric-default entry.

**Proof:** paste the new `exploration-policy.md` section + confirm `mkdocs build --strict`
(or the repo's doc-lint equivalent, if one exists) doesn't break on the new cross-link.

**Sub-parts (independent, dispatch as a build-wave):**
1. `exploration-policy.md` new intent section (the core content).
2. `trade-loops.md` cross-link paragraph.
3. `DECISIONS.md` Pending entry.
These three files don't conflict — safe to draft in parallel via subagent workers, then one
pass to sanity-check the cross-links resolve.
