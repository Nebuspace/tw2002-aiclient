# WO-AUDIT-WIRE-ACTION-SAFETY-COVERAGE-STARTUP-ASSERT

**Status:** CLAIMED by `impl-aiclient-cursor` (hub HEADS-UP 2026-08-04T16:26:42Z)
**Priority:** MED · **Gated:** no

## Goal

Call `action_safety.assert_coverage_map_intact()` from a live product path (app startup or equivalent boot) so a drifted guard/proof pin fails loud outside the dedicated test file.

## Scope

- `tw2002_aiclient/action_safety.py` (call only — no inventory redesign)
- App boot / `__main__` / entry that every normal launch hits
- Tests pinning the wire fires and a broken map fails closed
- This WO file

## Out of scope

- New external deps · rewriting the coverage registry · money-path / live TWGS

## Accept

1. Product path (not only tests) invokes `assert_coverage_map_intact()` on startup/boot.
2. Failure fails closed (exception / non-zero exit) — never silent skip.
3. Pins cover fire + inject-broken-map RED.
4. live-prove: `n/a` (offline integrity assert).

## Proof

Targeted pytest + suite green. STATUS with SHA.
