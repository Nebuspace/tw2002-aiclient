# WO-BUILD-CLI-STATE-VERB-SUBPARSER

**Goal:** Register `tw state` in `cli.py` `build_parser()`, dispatch to the existing daemon
`state` wire verb, with `--json` / `--run-dir` passthrough (mirrors `tw screen` / `tw status`).

**Scope:**
- `tw2002_aiclient/session/cli.py` — `cmd_state` + subparser
- `tests/test_cli_state_verb.py` — parser + send_request forwarding
- `tests/test_cli_log.py` / `tests/test_cli_ops_verb_c.py` — allowlist / docstring pins
- `canon/architecture/cli-verbs.md` + `canon/log.md` — tip-true LIVE (leave WIRE-ONLY)

**Depends-on:** none (protocol `state` already LIVE since WO-P2-G4-X1)

**Accept:**
- `./tw state --help` lists the verb
- `cmd_state` calls `send_request("state", {})` with resolved `--run-dir`
- `--json` prints the protocol envelope
- Canon marks `state` LIVE and removes it from the WIRE-ONLY-only bucket
- Offline suite green for touched tests

**Proof:** pytest on `tests/test_cli_state_verb.py` + `tests/test_cli_log.py` +
`tests/test_cli_ops_verb_c.py`; live-prove `n/a` (CLI wire over existing read-only protocol;
no login / no turns).

**Refs:** `canon/architecture/cli-verbs.md` Session primitives · `protocol.py` `verb == "state"`
