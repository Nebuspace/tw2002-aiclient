# WO-CANON-DRAFT-EXPLORE-SESSION-CONTINUITY

**Goal:** Document `sector_explore.ExploreRunner.start()` session-continuity —
same `Session` object, no second connection — and the post-#554 guardian
reconnect wait that stops false `halt_not_drivable:game_select` halts.

**Scope:**
- `canon/strategy/exploration-policy.md` (contract section)
- `canon/research/autopilot-live-drive-findings-2026-08-08.md` (Axis 5 post-fix)

**Accept:**
1. Canon states same-session reuse via daemon `ExploreRunner` + protocol dispatch.
2. Canon names `_gate_screen` halt vocabulary and `RECONNECT_WAIT_*` behaviour.
3. Research Axis 5 marked mitigated with pointer to the contract + live evidence.

**Proof:** Docs-only; suite green.
**Refs:** WO-AI-TRANCHE-9 item 5 · PR #554 · credit-doubling live-prove 2026-08-09.
