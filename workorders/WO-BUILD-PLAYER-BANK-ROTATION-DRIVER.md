# WO-BUILD-PLAYER-BANK-ROTATION-DRIVER

**Goal:** Surface the rotation-due decision without requiring the operator
to already know to run `tw players next` — per canon's "deferred future
work" framing (`canon/surfaces/entry-and-profile-selection.md:378-382`).

**Scope resolution (real design question, not a default):** the canon
citation's own words ("daemon-side... deciding whose turn it is across the
bank") suggest a cross-profile watcher process. This repo's hard rule is
**single-connection, single-session daemon** — one telnet socket per
profile — so there is no existing long-running process that spans the whole
player bank, and standing one up would be new standing infrastructure, not
a small addition. Scoped down to the safe, small half: mark the rotation-due
row in `tw players list`'s existing on-demand output, so the decision is
visible without a second command. **Not built:** an actual automated
cross-profile watcher/process. If that's what's wanted, it's a materially
different WO.

**Scope:**
- `tw2002_aiclient/players_cli.py` — `cmd_players_list`, `add_players_parsers`
- `tests/test_players_cli_list.py`
- this WO file

**Out of scope:** auto-login, auto-switch, any new daemon/watcher process
(all still explicitly deferred, matching `WO-BUILD-PLAYER-ROTATION-SELECTOR`'s
existing boundary — "never logs in / never auto-switches").

**Constraints:**
- Read-only: reuses the existing `player_bank.next_player` selector, no new
  credential/session-control surface.
- `tw players list` never opens the session socket (unchanged invariant).

**Accept:**
1. `tw players list` marks the row `next_player()` would select with a `→`
   prefix, using the same `--cooldown-hours` default/flag as `tw players next`.
2. No eligible row (empty bank, all cooling down) → no row marked, no error.
3. Existing `tw players list` behavior (boundary lines, broken-profile `!`
   marker, empty-bank line) unchanged.

**Proof:** `.venv/bin/python -m pytest tests/test_players_cli_list.py tests/test_player_bank.py -n0 -q` → 41 passed.
