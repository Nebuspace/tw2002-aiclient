# WO-BUILD-TRADE-CHAIN-CLI-VERB

**Parent:** `WO-ESCALATE-LIVE-DRIVE-DOUBLE-MONEY-FINDINGS` (hub live-drive 2026-08-06).

**Goal:** Expose live daemon RPC `trade_chain_start` / `trade_chain_stop` /
`trade_chain_status` as `tw chain start|stop|status`, mirroring `tw explore
start|stop|status`.

**Scope:**
- `tw2002_aiclient/session/cli.py` — thin `cmd_chain_*` + argparse subgroup
- `tests/test_cli_trade_chain_wiring.py` — parser + payload + exit codes
- `workorders/WO-ESCALATE-LIVE-DRIVE-DOUBLE-MONEY-FINDINGS.md` (commit findings)
- this WO file

**Out of scope:** explore StarDock skip (`WO-FIX-EXPLORE-SKIP-SPECIAL-PORTS`);
live witness (`WO-LIVE-WITNESS-FIRST-TRADE-LOOP`); TUI chrome; engine changes.

**Constraints:**
- Fail-closed: start requires `--world-id` + `--fingerprint` (human-confirmed chain).
- Optional `--cash-floor` / `--turn-reserve` default to
  `trade_chain.DEFAULT_CASH_FLOOR` / `DEFAULT_TURN_RESERVE`.
- No auto-fire; CLI only arms what the operator names.
- Hub GO: live-drive HANDOFF 2026-08-07T02:32Z / redirect 02:53Z.

**Accept:**
1. `tw chain --help` / `start|stop|status --help` exit 0.
2. `tw chain start --world-id X --fingerprint F` → `send_request("trade_chain_start", …)`.
3. stop/status → empty payload verbs.
4. Offline wiring tests green; live-prove `n/a` (CLI wiring; no live arm without Max sacrificial GO).

**Proof:** `pytest -q -n0 tests/test_cli_trade_chain_wiring.py`
