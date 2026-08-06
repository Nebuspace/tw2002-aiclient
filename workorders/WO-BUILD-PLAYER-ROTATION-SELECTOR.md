# WO-BUILD-PLAYER-ROTATION-SELECTOR

**Status:** in flight (impl-aiclient-cursor)  
**Priority:** LOW (Cycle-43)  
**Depends-on:** none

## Goal

Land a read-only rotation *selector*: `next_player(rows, *, cooldown_hours) -> str | None`
honoring a documented window gate, wired as `tw players next`. No auto-login / auto-switch
(that is `WO-BUILD-PLAYER-BANK-ROTATION-DRIVER`).

## Scope

- `tw2002_aiclient/session/player_bank.py` — `next_player` + `DEFAULT_ROTATION_COOLDOWN_HOURS`
- `tw2002_aiclient/players_cli.py` — `tw players next` (+ `--cooldown-hours`)
- `tw2002_aiclient/session/cli.py` — register `add_players_parsers` (thin)
- `tests/test_player_bank.py` — selector + CLI wiring pins
- `canon/surfaces/entry-and-profile-selection.md` — tip-stamp selector LIVE; driver still deferred

## Out of scope

- Daemon rotation driver / auto-login
- `tw players list` (separate residual)
- Updating `last_played` on session end

## Accept

1. Prefer `never`, then oldest out-of-window stamp; skip `error` rows and in-cooldown stamps.
2. Truncated / unparseable `last_played` fail closed when cooldown > 0.
3. `tw players next` prints the name (exit 0) or an honest empty message (exit 1).
4. Canon no longer claims selection is only "present" without a tip home.
5. Offline tests green.

## Proof

```bash
.venv/bin/python -m pytest tests/test_player_bank.py -q -k next_player
```

Live-prove: **n/a** (offline selector + CLI wiring; no session/login/play path).
