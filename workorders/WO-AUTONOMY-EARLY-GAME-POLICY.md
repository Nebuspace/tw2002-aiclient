# WO-AUTONOMY-EARLY-GAME-POLICY

**Goal:** Thin early-game autonomy scheduler that **offers** the top FOCUS
candidate for confirm-to-arm — never silent money-path fire.

## Why (full-autonomy drive)

After FOCUS (#278) and hold-upgrade (#279), the missing piece is a loop that
picks *what* to offer next: explore until executable chain or StarDock known,
then surface the ranked FOCUS top candidate for operator confirm. Autonomy =
client drives the loop; canon still forbids silent spend.

## Fix

1. **Policy module (pure):** given `status` (+ focus candidates, chain
   executability, StarDock known, empty holds), return one
   `AutonomyOffer` — `kind` ∈ {`explore`, `run_chain`, `upgrade`, `idle`}
   + reason string + gated flag. Prefer:
   - `explore` while no executable chain **and** StarDock unknown
   - else top ungated FOCUS candidate
   - gated upgrade/chain stay offerable but marked gated (confirm still required)
2. **Play surface:** one affordance (key / strip chip) that starts the existing
   confirm-to-arm path for that offer — reuses #267 / #279 arms; does **not**
   invent a new daemon spend verb.
3. **Pins:** policy never calls arm/send; incomplete status → `idle` with
   honest reason; hostile/missing focus → idle; explore never selected when
   an ungated executable chain exists (unless StarDock-seeking carve-out
   documented in WO).

## Accept

1. Unit pins for preference order (explore → chain → upgrade) on fixture status.
2. Offer path raises confirm gate only — never daemon money verb without
   confirm scaffold complete.
3. Does not weaken default-deny on trade/hold arms.
4. live-prove: **n/a** for policy-only; money-path live stays on #267/#279
   diversity when Max GO.

## Scope

- New `autonomy_policy.py` (or equivalent) + Play wire to confirm
- tests
- `workorders/WO-AUTONOMY-EARLY-GAME-POLICY.md`

## Constraints

- No silent auto-trade / auto-buy (would need Max DECISION)
- No new deps · additive only
- Depends on #278 FOCUS (on main) · prefers #279 hold arm present for
  `upgrade` offers (degrade: omit upgrade if arm absent)

## Proof

Offline pytest pins. Live n/a (display/offer only).

## Refs

- `.samantha/plans/full-autonomy-early-game.md` step 5
- #278 `WO-PRIORITY-ENGINE-FOCUS-WIRE`
- #279 `WO-STARDOCK-HOLD-UPGRADE-ARM`
- #267 guarded chain confirm scaffold
