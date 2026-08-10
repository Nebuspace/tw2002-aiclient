# WO-CANON-FIX-EXPLORATION-POLICY-CHAIN-HUNT-DEFAULTS-TIP-TRUE

**Status:** DONE (this PR)
**Priority:** MED (docs honesty / tip-true residual after #668)
**Claimed-by:** impl-aiclient-cursor
**Source:** idle residual hunt 2026-08-10 after #668 MERGED (`715517d1`); cycle-49 + prior tip-closed ghosts skipped

## Goal

Tip-true `canon/strategy/exploration-policy.md` Chain-hunt mechanism prose that still said numeric
depth/turn caps "must be ruled before the follow-on build WO hard-codes them" — tip-false after
`#640`/`#641` shipped required-flag arming and `#668` tip-trued DECISIONS to **defaults only**.

## Verify-first (origin/main @ 715517d1)

- Stale: exploration-policy.md ~165-168 — "before the follow-on build WO hard-codes them"
- Tip LIVE: `session/cli.py` requires `--exhaust-depth` + `--turn-budget` for `chain_hunt` (no defaults)
- Already tip-true: DECISIONS `PENDING-CHAIN-HUNT-…` (#668); Schema arming cycle (#667)
- Lag: exploration-policy mechanism paragraph still implied build was gated on the Pending

## Out of scope

- Do not invent depth/turn **defaults** (still Max-gated Pending numerics)
- Do not touch Max-gated `WO-ESCALATE-BOUNDED-REPEAT-*`
- Do not rebuild Chain-hunt planner/CLI (shipped)

## Accept

1. Mechanism paragraph states tip requires caller flags; Pending = optional built-in defaults only.
2. Code divergence records the stale "follow-on build WO hard-codes" claim as closed.
3. live-prove: n/a (docs-only).

## Refs

- `canon/strategy/exploration-policy.md` (§ Explicit hop-cost tradeoff · Code divergence)
- `canon/DECISIONS.md` § PENDING-CHAIN-HUNT-SIBLING-EXHAUST-DEPTH-TURN-CAP (`#668`)
- PR `#640` / `#641` / `#667` / `#668`
