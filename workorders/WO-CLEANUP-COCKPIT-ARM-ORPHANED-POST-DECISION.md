# WO-CLEANUP-COCKPIT-ARM-ORPHANED-POST-DECISION

**Status:** OPEN (in PR)  
**Priority:** MED (tranche-6 #8)  
**Claimed-by:** impl-aiclient-cursor  

## Goal

Delete orphaned `tw2002_aiclient/cockpit/arm.py` after DECISION `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` retired the separate ARM chip from `screens.py` draw wiring.

## Tip-verify

| Check | Result |
|---|---|
| Product imports of `cockpit.arm` | **0** (only `control_seat` imported `ARM_GAP` — inlined) |
| Live draw path | Merged trainer seat chip; `screens.py` does not call `compose_arm_chip` |
| `armconfirm.py` | **Keep** — unrelated confirm gate |

## Diff

- Delete `cockpit/arm.py` + `tests/test_cockpit_arm.py`
- Update `control_seat.py` (inline `_ARM_SEPARATOR`), dependent tests
- Keep `test_cockpit_arm_wiring.py` / `test_cockpit_arm_pty.py` (merged-chip proofs)

## Accept

- [ ] `rg cockpit\.arm` — no product imports
- [ ] Targeted pytest green on arm-wiring / arm-pty / autoloop / status-redaction

## Proof

```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/python -m pytest \
  tests/test_cockpit_arm_wiring.py \
  tests/test_cockpit_arm_pty.py \
  tests/test_autoloop.py \
  tests/test_status_prompt_redaction.py \
  tests/test_mode_badge_vocabulary.py \
  tests/test_never_auto_action.py -q -n0
```

## live-prove

`n/a` — dead-module retirement; no live play-path change.
