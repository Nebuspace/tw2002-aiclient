# WO-WIRE-MENUMAP-NAV-EXEC

**Status:** IN FLIGHT · Cursor · `wo/WIRE-MENUMAP-NAV-EXEC`
**Priority:** MED
**Gated:** no (canon residual after WO-BUILD-DETERMINISTIC-NAV-EXECUTOR)

## Goal

Wire `menu_nav_exec.run_nav` into `tw menumap` so a planned route can send
under an explicit human arm flag.

## Accept

1. `tw menumap --to SIG --exec` without `--arm` → exit 1, zero sends.
2. `tw menumap --to SIG --exec --arm` → calls `run_nav` via daemon do/screen
   adapter (menu keys without trailing Enter).
3. Canon divergence stamps CLI consumer LIVE.
4. live-prove: n/a (offline pins + daemon adapter unit/monkeypatch; no TWGS arm).

## Proof

```bash
.venv/bin/python -m pytest tests/test_cli_menumap.py tests/test_nav_exec.py -q -n0
```
