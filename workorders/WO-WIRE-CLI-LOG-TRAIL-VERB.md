# WO-WIRE-CLI-LOG-TRAIL-VERB

**Status:** DONE (pending merge)
**Priority:** LOW
**Gated:** no

## Goal

Wire `tw log` / `tw trail` to `ledger.read_entries` + `render_trail_line`
(daemon-free filesystem trail).

## Scope

- `tw2002_aiclient/session/cli.py` — `cmd_log` + `log`/`trail` parsers
- `tests/test_cli_log.py` — flip not-wired pins to behavior pins
- This WO file

## Accept

1. `tw log --ledger <path>` prints trail lines; `--n` keeps most-recent N.
2. `tw trail` is the same handler.
3. Missing ledger → empty stdout, exit 0.
4. live-prove: `n/a` (CLI filesystem read; no live session delta).

## Proof

`pytest tests/test_cli_log.py -n0`
