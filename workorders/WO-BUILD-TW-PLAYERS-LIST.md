# WO-BUILD-TW-PLAYERS-LIST

**Status:** IN FLIGHT · Cursor · `wo/BUILD-TW-PLAYERS-LIST`
**Priority:** MED
**Gated:** no

## Goal

Close the canon residual on `entry-and-profile-selection.md`: wire
`tw players list` so the CLI touchpoint prints the same no-collusion boundary
lines as `BankViewScreen`, then `player_bank.list_players` rows.

## Accept

1. `tw players list` registered; prints `BOUNDARY_LINE_1` / `BOUNDARY_LINE_2` first.
2. Empty bank uses `BANK_EMPTY_LINE`; unreadable bank → exit 2.
3. Broken profiles marked (name`!` + `error:` line).
4. Never logs in / never opens session socket.
5. Canon residual bullets updated.
6. live-prove: n/a (filesystem metadata only).

## Proof

```bash
.venv/bin/python -m pytest tests/test_players_cli_list.py tests/test_player_bank.py tests/test_cli_log.py -q -n0
```
