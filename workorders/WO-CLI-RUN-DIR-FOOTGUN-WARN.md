# WO-CLI-RUN-DIR-FOOTGUN-WARN

**Status:** **DONE** · origin `368c4c9` (`368c4c90e2a968c7d8b29c2ce8a37e4356981b87`) · product (`session/cli.py` + pin) · Cursor seat 2026-07-26
**Posted:** 2026-07-26 · matrix collateral: `./tw status|stop` without `--run-dir` hit **default** daemon while `TW_CONFIG_DIR` was isolated

## Goal

Make the `--run-dir` / default-run-dir footgun **loud before damage**: isolating `TW_CONFIG_DIR`
does **not** isolate the daemon socket axis. Operator must not silently stop/status the wrong daemon.

## Scope

- CLI help / error / HEADS-UP path for `status`/`stop`/`ensure` when invoking without `--run-dir`
  while another isolation signal is present (`TW_CONFIG_DIR` set, or non-default config dir)
- Optional: refuse or require confirm when default run-dir would target a live daemon and the
  caller's config dir is not the default — **no** silent multi-daemon kill
- Docs one-liner in ops/canon if a verb surface exists
- **Out:** changing default run-dir resolution itself (already DONE via WO-P2-021)

## Accept

- Repro of the matrix footgun shape fails closed or warns with the actual run-dir path printed
- Pin test covers the warn/refuse path
- Stay out of `WO-SUITE-PARALLEL-FLAKE` test files if CC still owns that lane

## Proof

Tip `368c4c9`. `pytest tests/test_cli_run_dir_footgun_warn.py -n0` — 6 passed. No live default-daemon touch.
