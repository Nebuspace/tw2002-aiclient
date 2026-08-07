# WO-FIX-BANKVIEW-BROKEN-PROFILE-ERROR

**Status:** IN FLIGHT · Cursor · `wo/FIX-BANKVIEW-BROKEN-PROFILE-ERROR`
**Priority:** MED
**Gated:** no

## Goal

`player_bank.list_players` already surfaces broken profiles with an `error`
key, and `tw players list` marks them — but `BankViewScreen` still painted
six ordinary columns. Close the TUI half so broken = visible + diagnosable.

## Accept

1. Broken row shows `name!` (warn tone) + `error: …` follow-up line.
2. Healthy rows unchanged.
3. `player_bank` docstring + entry-surface canon residual updated.
4. live-prove: n/a (offline curses recording pin).

## Proof

```bash
.venv/bin/python -m pytest tests/test_bank_no_collusion_banner.py -q -n0
```
