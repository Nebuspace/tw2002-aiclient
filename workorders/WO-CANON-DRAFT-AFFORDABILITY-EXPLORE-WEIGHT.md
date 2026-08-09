## WO-CANON-DRAFT-AFFORDABILITY-EXPLORE-WEIGHT

**Goal:** Draft canon for a new FOCUS ranking input — once current credits cross the cost of a
cargo-hold upgrade or fighter purchase, raise the `explore` candidate's weight (a louder
suggestion, never an autonomous switch) so the operator is nudged toward finding a StarDock/new
loops instead of only being shown the currently-known chain.

**Origin:** Max, 2026-08-09, same session as `WO-CANON-DRAFT-CHAIN-MAXIMIZING-EXPLORE-STRATEGY`.
Framing: a bot running an inefficient 3-hop loop because it's all it has should start weighing
exploration higher once it could actually afford to act on what exploring finds (upgrades,
fighters), since at that point grinding the same loop stops being the only rational move.

**Verify-first findings (re-verified 2026-08-09 via a dedicated research pass, not assumed):**
- No code today compares current credits against `hold_upgrade_quote` / `fighter_unit_price` and
  feeds the result into explore weighting. Confirmed by grep across `focus_status.py`,
  `priority_engine.py`, `autonomy_policy.py` — no match.
- The plumbing to build this from is already partly there:
  - `priority_engine.afford_fighters()` (`priority_engine.py:215-309`) already computes
    affordability (credits vs. `fighter_unit_price`/`hold_upgrade_quote`, spending-priority
    ordered: trade float → hold upgrade → fighters) — but its output only feeds a GOALS status
    label (`fighter_buy_status_label`), never explore weighting.
  - `chain_depletion.depletion_signals()` (`chain_depletion.py:148-165`) already computes and
    writes `explore_appetite_raised` onto chain status — but **nothing reads it**. This is the
    natural signal to extend/reuse rather than inventing a second, parallel "explore appetite"
    concept.
  - `focus_status.recommend_focus_candidates()` (`focus_status.py:214-312`) is where prerequisite
    -unknown booleans already boost the explore candidate's `overlay_weight` — the same seam a
    credits-crossed-threshold boost would plug into.
- Nearest existing built behavior (`priority_engine.upgrade_gate_while_chaining`,
  `priority_engine.py:103-167`) only fires **mid-chain**, comparing round-trip detour cost to a
  *known* StarDock against upgrade payback. It never initiates a fresh explore push the moment
  credits clear a threshold while idle/between runs — that's the actual gap.

**Scope (canon-draft phase — this WO):**
- `canon/engine/priority-engine.md` — extend the 13-objective weighted catalog (or add a new
  entry) to name this trigger explicitly: credits ≥ known hold-upgrade or fighter cost raises the
  `explore` candidate's `overlay_weight`. Specify it as reusing `explore_appetite_raised`'s
  existing plumbing (give depletion and affordability a shared consumer, not two disconnected
  signals) rather than inventing a parallel flag.
- `canon/strategy/exploration-policy.md` — add affordability as a second named trigger for the
  "explore/exploit appetite" section, alongside the existing depletion trigger, with the same
  "input to ranking, never a live picker" framing already established there.
- `canon/DECISIONS.md` — file Pending: what counts as "affordable" (raw credits ≥ cost? some
  safety-margin buffer above trade float?), and whether hold-upgrade and fighter thresholds
  should weight explore differently (e.g. hold upgrade being cheaper/more directly loop-enabling
  might warrant a stronger nudge than a fighter purchase).

**Explicitly NOT in this WO's scope:** the actual code (wiring `afford_fighters`'s comparison
into `focus_status.py`'s weight calculation, and hooking up `explore_appetite_raised` as an
actual consumer). Follow-on build WO once this canon draft and
`WO-CANON-DRAFT-CHAIN-MAXIMIZING-EXPLORE-STRATEGY`'s sibling companion are both reviewed — the
two land together well since both touch FOCUS's explore weighting.

**Constraints:** Ungated — no auth/payments/MFA/admin/AI-safety surface. Preserve the existing
invariant (already canon, `trade-loops.md:106-115`) that any appetite/weight change is a ranking
input only — rotation off a running loop stays operator-decided, never autonomous, even once this
ships.

**Accept:**
- New trigger named explicitly in `priority-engine.md` and `exploration-policy.md`, at the same
  detail level as the existing depletion trigger.
- Explicitly ties the new trigger to reusing `explore_appetite_raised` rather than a new flag —
  don't let this WO accidentally spec a second competing signal.
- `DECISIONS.md` carries the Pending affordability-threshold-definition entry.

**Proof:** paste the new/extended sections in STATUS.

**Sub-parts (independent, dispatch as a build-wave):**
1. `priority-engine.md` catalog extension.
2. `exploration-policy.md` second-trigger addition.
3. `DECISIONS.md` Pending entry.
