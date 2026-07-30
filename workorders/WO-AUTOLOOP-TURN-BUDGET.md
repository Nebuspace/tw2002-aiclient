# WO-AUTOLOOP-TURN-BUDGET — fail-closed turn-budget rail on AutoLoopRunner

**Status:** DONE · origin `2a969e6` (#241) · Accept verified 2026-07-30
**Posted / seeded:** 2026-07-30T05:17Z · hub (IDLE-KICK after offline teach loop closed)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `5b1afb5` · `Session.turns_snapshot` / `observe_turns` LIVE (HUD bridge)  
**Refs:** `session/autoloop.py` "One pass, and why there is STILL no cycles" · `canon/doctrine/action-safety-guards.md` § Structural rails · `#239` scope schema-only

## Why now

Operators can type `scope: repeating` (#239) but arm remains one-pass because
autoloop still lacks **two of four** repeating rails: **turn-budget** and
**hazard-halt**. Turns observation now exists (`turns_snapshot`). This WO
lands the turn-budget rail only. `cycles` stays **refused** until hazard-halt
also lands — never accept `cycles=N` and run once.

## Goal

Give `AutoLoopRunner` / `autoloop_start` a real, enforced **turn-budget**
that fails closed when turns are unknown/stale/unreadable or the budget is
exhausted — mirroring the credit-floor posture (X5).

## Scope

- Accept a narrow `turn_budget` (non-negative int; refuse bool/float/negative
  / unknown types) on `autoloop_start` / runner start — **only** because it
  will be enforced.
- Before each pass/send boundary (same choke-point family as floor): read
  `turns_snapshot`; halt with typed reasons when unknown / stale /
  unreadable / budget exhausted (pick closed codes consistent with existing
  halt vocabulary; do not invent free-text).
- A run that requests a turn budget against a session that cannot observe
  turns → refuse at arm (`turn_budget_unsupported` or house equivalent) —
  never arm blind.
- Focused tests + mutation where feasible (minted proceed-on-unknown goes red).
- Update the "One pass / STILL no cycles" docstring tally: turn-budget →
  built; hazard-halt still NOT; `cycles` still refused.

## Constraints

- **`cycles` / `force` / `param` remain REFUSED** — this WO does not unlock
  repetition.
- Do not change Play `V` / reflex_arm semantics (still one-pass via
  autoloop_start).
- `#218` `app.py` split frozen — prefer `autoloop.py` / `protocol.py` /
  player choke-point; smallest `app.py` only if STOP banner label requires it.
- No §A.2 / new deps / tooling riders.
- Live successful multi-cycle arm still Max-gated later; this WO live prove:
  `n/a` (offline rail) unless hub asks a safe refusal half.

## Accept

1. `autoloop_start` with valid `turn_budget` arms only when turns are
   observable; otherwise typed refusal, zero launch.
2. Mid-run: unknown/stale/unreadable turns or exhausted budget → halt with
   typed reason; no further sends.
3. `cycles` still refused (pin).
4. Docstring tally updated (3 of 4 rails built after this; hazard still out).
5. Focused tests + full suite green.
6. Live prove: `n/a` (control/rail; no new TWGS send path required).

## Proof

```bash
pytest -q tests/test_autoloop.py  # + new focused turn-budget pins
pytest -q tests
```

STATUS names the halt codes and confirms `cycles` still refused.

## Follow-on (not this WO)

- `WO-AUTOLOOP-HAZARD-HALT` → then `cycles` / `scope: repeating` run-loop.
- Max sacrificial GO: live `V`→`y` arm (#235 NOT-ATTEMPTED).
