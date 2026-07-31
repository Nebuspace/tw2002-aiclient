# WO-PLAY-STRIP-POLICY-AUTO

**Status:** READY · BANKED · HIGH · Max GO 2026-07-31 (trainer strip redesign wave 3/3)
**Seat:** `impl-aiclient-cursor` (after WO1 chrome; preferably after WO2 layout)
**Branch:** `wo/PLAY-STRIP-POLICY-AUTO` (hub seeds at HANDOFF)
**Depends:** DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` · WO-PLAY-STRIP-TRAINER-CHROME on `main`

## Why

Chrome alone does not make a trainer. Max ruled **App-armed auto = default**: under `APP-ARMED` + policy toggles ON, App shows and does without per-action `y`. Leaving App → Manual **is** the halt (STOP/PANIC redundant). Port/Cargo/Ship ·ON/OFF must gate App behavior.

## Goal

Wire policy + halt semantics to match the DECISION.

## Scope

1. **Halt = Mode leave:** Ctrl-A to `MANUAL-HUMAN` stops explore / autoloop / chain / hold runners (same family as today’s panic/Esc stops). Retire calm-path dependency on Panic key (handler may remain for compat or map to Mode leave — document).
2. **Port Trade ·ON/OFF** gates App port-trade pursuit (default ON).
3. **Cargo Hold Upgrade ·ON/OFF** gates App hold-buy path (default ON); retire strip `H)old?` one-shot as required path.
4. **Ship Upgrade ·ON/OFF** gates App ship-upgrade path (default ON); honest no-op if engine not ready.
5. **App-armed auto:** under APP-ARMED + relevant ·ON, loop/hold/ship may proceed **without** per-action confirm (LOGS audit). Manual still sovereign.
6. Update HELP / autonomy help lines to match (no Offer/Hold confirm doctrine on calm path).
7. Pins for Mode-leave stops runners; toggles gate; no silent spend when ·OFF or MANUAL.
8. This WO file on the branch.

## Out of scope

- Chrome-only paint (WO1) · gutter nest (WO2).
- #283 sacrificial live diversity (separate Max GO) — this WO may need live-prove **success** diversity if money-path touches play/session; hub will require probe evidence.

## Constraints

- Safety list: money-path — Max already GO’d App-armed default; still no prod / no force-push.
- Panic vocabulary retired from operator teaching; escalation yield banner may say “Manual” not “STOP control”.

## Accept

1. `^A` to Manual stops live App runners.
2. P/C/S ·OFF prevents App auto on that path; ·ON allows under APP-ARMED.
3. No per-action `y` required for calm App-armed paths covered by this WO.
4. Suite green · live-prove per hub ritual (product money-path → diversity bar or hub pushback).

## Proof

```bash
.venv/bin/python -m pytest tests/test_play_panic_wire.py tests/test_cockpit_mode*.py tests/test_ensure_no_auto_arm.py -n0 --tb=line
# + new pins for Mode-leave halt + toggle gates
```

## Refs

- `.samantha/plans/play-strip-autonomy-keys.md`
- Prior confirm-not-auto scars — superseded for calm trainer path by DECISION
