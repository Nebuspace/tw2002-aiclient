# WO-P3-HARNESS-REHAB — Layer-B pty helpers (D1)

> Status: **DONE** · origin `49b21a1` (hub Accept stamp 2026-07-26 · was EXECUTE DONE awaiting Accept)
**Phase:** 3 · **Type:** test-rehab · **Depends:** Phase-3 cockpit PREP D1
**Goal:** Unblock Phase-3 Layer-B proofs — shared FakeClient + pty/pyte helpers import
`tw2002_aiclient` only (no archive `twclient`).

## Shipped

| Path | Role |
|------|------|
| `tests/fake_client.py` | Scripted watch-event FakeClient |
| `tests/pty_helpers.py` | openpty capture, pyte grid/find_text/cell_at, winsize |
| `tests/test_pty_helpers.py` | Helper unit proofs |
| `tests/test_pty_helpers_smoke.py` | Collect/import-green + no-`twclient` AST gate |

## Explicitly deferred (still `--ignore`d)

`test_spectate_layout` · `test_spectate_app` · `test_interactive_app` · `test_aiclient_play_panels`
(+ adjacent control_panel / intervention_labels) — rewrite onto helpers under owning PWO
execute (Fable geometry for layout; Esc→launcher for 030).

## Proof

```bash
.venv/bin/python -m pytest tests/test_pty_helpers.py tests/test_pty_helpers_smoke.py -q
.venv/bin/python -m pytest --collect-only -q   # 0 ERRORS
rg -n '^import twclient|^from twclient' tests/fake_client.py tests/pty_helpers.py tests/test_pty_helpers*.py
# expect no match
```
