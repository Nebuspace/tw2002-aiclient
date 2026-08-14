# WO-BUILD-ROTATION-NOTIFY-ONLY-SURFACE

**Goal:** Surface `advance_rotation()` as a **passive notify-only** CLI check
so operators can see "X is due, rotate?" without auto-login / auto-switch.
This is DECISIONS.md `PENDING-PLAYER-ROTATION-AUTO-SWITCH-CONSUMER` option (b)
— the ungated half. The auth-adjacent daemon auto-switch consumer stays Max-gated.

**Depends-on:** `WO-BUILD-PLAYER-BANK-ROTATION-DRIVER` (landed — `RotationDecision`
+ `tw players rotate` already exist).

**Scope:**
- `tw2002_aiclient/players_cli.py` — `format_rotation_notify(decision)` helper +
  `tw players rotate --check` flag on the existing verb.
- `tests/test_players_cli_rotate.py` — pins for `--check` due / none_eligible /
  empty_bank / unreadable + exit-code contract.
- this WO file.

**Out of scope:**
- Cockpit / mode-line / daemon consumers.
- Auto-login, auto-switch, control-lock changes, any socket send.
- Any `last_played` write path.
- Changing non-`--check` `tw players rotate` behavior.

**Constraints:**
- Still decide-and-report only; never mutate the bank.
- `--check` passes already-fetched rows into `advance_rotation` (no second
  default `list_players` read).
- No new external dependencies.
- No operator-home absolute paths in committed artifacts.

**Accept:**
1. `tw players rotate --check` with a due profile prints a notify line that
   names the profile and states notify-only / no auto-switch; exit 0.
2. `--check` with empty bank or none eligible prints a reason-bearing notify
   line; exit 0 (inquiry succeeded — nobody due is not a failure under check).
3. `--check` on `BankUnreadable` exits 2 (unchanged unreadable contract).
4. Plain `tw players rotate` (no `--check`) keeps name-only / exit-1 behavior.
5. No product path under this WO opens a session or writes `last_played`.

**Proof:** `.venv/bin/python -m pytest tests/test_players_cli_rotate.py tests/test_player_bank.py -n0 -q`
