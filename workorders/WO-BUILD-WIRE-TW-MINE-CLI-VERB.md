# WO-BUILD-WIRE-TW-MINE-CLI-VERB

**Status:** in flight (impl-aiclient-cursor)  
**Priority:** HIGH (queue READY)  
**Depends-on:** none

## Goal

Expose the existing `miner.mine_ledger` engine as `tw mine` / `tw patterns`
CLI verbs (filesystem-only; inert drafts; never sends).

## Scope

- `tw2002_aiclient/mine_cli.py` — new (line-cap carve-out like `players_cli`)
- `tw2002_aiclient/session/cli.py` — register parsers
- `tests/test_cli_log.py` — shipped-verb allowlist + parse pins
- `canon/architecture/cli-verbs.md` — TARGET → LIVE
- this WO file

## Accept

1. `tw mine --help` / `tw patterns --help` register with `--min-support` and `--top-k`.
2. `--no-propose` ranks without writing drafts; default may write under drafts dir.
3. ASCII help inventory green; `_SHIPPED_VERBS` includes `mine` + `patterns`.
4. `cli-verbs.md` marks the verb LIVE.

## Proof

```bash
.venv/bin/python -m pytest tests/test_cli_log.py tests/test_cli_help_ascii_inventory.py -q -n0
.venv/bin/python -c "from tw2002_aiclient.session.cli import build_parser; build_parser().parse_args(['mine','--no-propose'])"
```

Live-prove: **n/a** (offline ledger mining; no session/login/play path).
