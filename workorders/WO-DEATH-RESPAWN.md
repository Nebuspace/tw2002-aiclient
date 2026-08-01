# WO-DEATH-RESPAWN

**Status:** READY · banked until #307 merges · HIGH · Max live 2026-08-01  
**Seat:** `impl-aiclient-cursor`  
**Branch:** `wo/DEATH-RESPAWN`  
**Depends:** `main` ≥ `ad0aff8` · after **#307** WARP-CONFIRM (avoid→N) lands  
**Max ruling:** On escape-pod destroyed / “start over from scratch,” **create a new character and start over**.

## Why (live)

Avoid-sector warp confirmed → space mines → escape pod destroyed → TWGS returns to game-select menu (`Enter your choice:` / Trade Wars 2002). Play/explore halt; same TCP still has `game_select_answered=True` so blind re-`ensure` can refuse a second door letter until stagnant re-entry. Operator stuck; Max wants automatic **new character** + resume.

## Goal

When App-armed (or ensure/Play recovery) observes **character-dead / start-over** and lands on `game_select` (or equivalent door), automatically: clear door flags → register a **new** character (mint handle/password, persist secrets) → reach `main_command` → ready for App-armed explore/trade again.

## Scope

1. **Detect** death/start-over honestly (screen text and/or transition to `game_select` mid-session after play — pins from Max paste / fixture). Do not invent death from unrelated game_select.
2. **Door:** clear `game_select_answered` / `game_select_letter_sent` for genuine mid-connection return (reuse stagnant re-entry kernel or explicit death latch).
3. **Register:** recovery path may force `allow_register` for this respawn (Max GO); mint new handle+password via existing credentials helpers; write secrets; complete `char_create` / password dance; update profile handle if required by current contract.
4. **Resume:** ensure/`login.run` to `main_command`; Play status_line/LOGS: honest “respawned as {handle}” (no password). Re-arm App explore policy if was App-armed.
5. Pins + this WO on branch. Public-repo safe (no secrets in logs).

## Out of scope

#307 warp avoid→N (separate) · counter-haggle · editing TWGS avoid list on server · multi-pod “been on today” edge unless it blocks Accept.

## Accept

1. Fixture/simulated death → game_select → new char registered → `main_command` without human keystrokes (profile recovery path).
2. Returning-alive `game_select` misfire still must not double-answer (stale buffer discipline preserved).
3. Suite green; live-prove NOT-ATTEMPTED or success if Cursor can safely prove on sacrificial profile.

## Proof

pytest + STATUS. No self-merge.

## Refs

Max paste 2026-08-01 · `login.py` game_select once-per-connection · `credentials.mint` · `allow_register`
