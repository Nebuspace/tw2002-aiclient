# WO-FIX-COCKPIT-ATTACH-CTRL-BRACKET-REGRESSION

**Status:** CLOSED · already matches Max ruling · tip verify `origin/main` `c94c592` · 2026-08-08T15:03:46Z
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/FIX-COCKPIT-ATTACH-CTRL-BRACKET-REGRESSION` (docs-only close)
**Refs:** queue-aiclient.md:348 · Max ruling 2026-07-25 (Ctrl-] from App-hold = deliberate no-op) · `workorders/WO-AUDIT-CTRL-RBRACKET-APP-HOLD.md` · `tests/test_cockpit_attach.py:1033-1091`

## Verdict

**CLOSED — no product fix.** On tip, Ctrl-] from App-hold does **not** mutate `status_line` (including any `explore_unavailable` path). Behavior already matches the 2026-07-25 owner ruling. Queue claim does not reproduce.

## Verify-first (tip `c94c592` / `c94c592`)

| Claim | Evidence |
|---|---|
| Max ruling = no-op stay App | `WO-AUDIT-CTRL-RBRACKET-APP-HOLD.md` EXECUTED/Ruled 2026-07-25; pin test docstring cites same |
| Pin test green | `pytest tests/test_cockpit_attach.py::test_ctrl_bracket_from_app_hold_is_a_no_op_state_unchanged_deliberately_ruled -n0` → pass; asserts `status_line` unchanged, `spectating`/`attached` false, lock stays App, no wire |
| Detach branch only when attached | `app.py::_run_play`: `if attach_conn is not None and key != 27:` then `if key == _DETACH_KEY` (`_DETACH_KEY = 29`) — App-hold has `attach_conn is None`, so Ctrl-] never enters detach |
| Unattached key path | Falls through to `play.handle_key(29)`; `PlayShellScreen.handle_key` has no branch for 29 → `None` (ordinary unmapped no-op) |
| No Ctrl-]→explore_start | Explore start is `E` / offer keys / policy arm paths only — not key 29. `explore_unavailable` lives on protocol explore_start/stop when runner missing (`session/protocol.py` ~702/~743); cockpit surfaces as `explore did not start — {reason}` / status-poll strings, not via Ctrl-] |

## Rejected product change

Do **not** invent a Spectate transition from App-hold (ruling forbids it). Do **not** special-case key 29 in `handle_key` just to "look fixed" — the no-op mechanism is already correct.

## Accept (this close)

1. Docs-only WO lands stating CLOSED + verify-first table.
2. Pin test remains green on tip (no code change).
3. live-prove: n/a (docs-only; offline pin already covers the ruled no-op).
