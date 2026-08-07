# WO-FIX-EXPLORE-NO-DEFENSIVE-POSTURE-BEFORE-UNCHARTED

**Goal:** Before map-fill explore commits to uncharted warps, attempt a
bounded defensive-fighter posture when a StarDock dealer is known within a
small turn budget — reducing how often stock-6 / 100k-credit ships die to
random hostile stacks (companion to hang-handling `#516`).

**Scope:**
- `tw2002_aiclient/session/explore_defensive_posture.py` (pure decision)
- `tw2002_aiclient/session/sector_explore.py` (map-fill pre-phase wire)
- tests + this WO

**Out of scope / residual:** taught auto-spend of credits at StarDock
(canon `ship-progression.md` keeps credit leave human-approved). This WO
**routes to the dealer and halts** `halt_defensive_posture:buy_<qty>` so a
human (or a follow-up taught buy macro under Max GO) can purchase. No new
stall when the dealer is unknown/unreachable/unaffordable — explore continues
as today.

## Policy numbers (judgment — escalate if Max wants different defaults)

| Knob | Value | Rationale |
|------|-------|-----------|
| Fighter floor | **20** | Archive `EconCaps.keep_min_defense_fighters`; stock start ~6 |
| Credit-fraction ceiling | **10%** | Caps spend on a fresh 100k pool (≤10k); typical top-up ≪ that |
| Unit price default | **100 cr** | Archived Class-0 placeholder until introspected |
| Dealer detour turn ceiling | **20** hops≈turns | Small; skip rather than hunt |
| Cash floor after buy | **10_000** | Archive `EconCaps.cash_floor` |

## Accept

1. Under-floor + funded + dealer within ceiling → explore seeks StarDock then
   halts `halt_defensive_posture:buy_<qty>` (purchase attempt surface).
2. No dealer / scarce turns / unknown fighters|credits / cannot afford →
   map-fill proceeds unchanged (no hang).
3. Policy numbers documented here + module docstring.

## Proof

- Offline: `tests/test_explore_defensive_posture.py`
- Live: sacrificial under-floor run with known StarDock → named halt before
  uncharted death; unreachable-dealer run explores as today.

## Refs

Design brief: `audit/design-briefs/wo-fix-explore-no-defensive-posture-before-uncharted.md`
Companion: `WO-FIX-EXPLORE-SHIP-DESTRUCTION-HANG` / PR #516
