# WO-CANON-FIX-DECISIONS-CHAIN-HUNT-WIRED-TIP-TRUE

**Status:** DONE (this PR)
**Priority:** MED (docs honesty / Scroll-Law residual)
**Claimed-by:** impl-aiclient-cursor
**Source:** idle residual hunt 2026-08-10 after cycle-49 / #667; queue ~595-603 candidates all tip-closed ghosts

## Goal

Tip-true `canon/DECISIONS.md` `PENDING-CHAIN-HUNT-SIBLING-EXHAUST-DEPTH-TURN-CAP` kernel item 2:
stop claiming Chain-hunt Implementation / CLI / panel wiring is a follow-on build WO after
`#640` / `#641` shipped planner + CLI arming. Keep the Pending scoped to **numeric defaults only**.

## Verify-first (origin/main @ c2582e6a)

- Stale: DECISIONS kernel item 2 — "Implementation / CLI / panel wiring stays a **follow-on build WO**"
- Tip LIVE: `explore.py` `INTENT_CHAIN_HUNT` / `plan_chain_hunt`; `session/cli.py` requires
  `--exhaust-depth` + `--turn-budget` with no invented defaults
- Already tip-true: `exploration-policy.md` Schema + Code divergence (#667) — DECISIONS lagged

## Out of scope

- Do not invent depth/turn **defaults** (still Max-gated Pending numerics)
- Do not touch Max-gated `WO-ESCALATE-BOUNDED-REPEAT-*`
- Do not build `WO-BUILD-CHAIN-HUNT-SIBLING-EXHAUST-EXPLORE` (superseded by #640/#641)

## Accept

1. DECISIONS kernel item 2 states tip wiring LIVE with PR cites; Pending = defaults only.
2. Status / "Needs human ruling" wording no longer implies CLI is unbuilt.
3. live-prove: n/a (docs-only).

## Refs

- `canon/DECISIONS.md` § PENDING-CHAIN-HUNT-SIBLING-EXHAUST-DEPTH-TURN-CAP
- `canon/strategy/exploration-policy.md` (§ Schema · Code divergence)
- PR `#640` / `#641` / `#667`
