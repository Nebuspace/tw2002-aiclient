# WO-P3-030 lane 2 — Daemon-survival VERIFY

> Status: **VERIFY PASS (structural)** · 2026-07-24 · seat: Cursor execute · no Fable chrome
> Canon: ADR-001 (app-disposable / daemon-continuity) · PREP `WO-P3-030-033-cockpit-frame-PREP.md` §PWO-030
> Out of scope: Mode-line N5 "Stop the daemon too? (Yes/No)" exit-confirm (`trainer-cockpit.md` N5 / Phase 5)

---

## Verdict

**Esc → launcher does not tear down the session/daemon.** Proven structurally + by unit test.
Full Layer-B pty + live-FakeSession "tw status still alive" leg is **not** claimed here — see gap below.

---

## Evidence (file:line)

| Claim | Cite |
|---|---|
| Esc returns router `"back"` (ends TUI binding only) | `tw2002_aiclient/screens.py:354-355` |
| Footer copy: return to launcher | `tw2002_aiclient/screens.py:347` · docstring `screens.py:298` |
| `_run_play` returns `"back"`/`"quit"` with **no** stop/teardown call | `tw2002_aiclient/app.py:151-152` |
| AST of `_run_play`: only `PlayShellScreen` / `draw` / `ensure_session` / `getch` / `handle_key` | `tw2002_aiclient/app.py:133-152` |
| Launcher on play `"back"`: redraw loop continues; **no** stop | `tw2002_aiclient/app.py:255-262` |
| `adapters` has ensure only — **no** stop/teardown API | `tw2002_aiclient/adapters.py:63-100` |
| ADR-001 exit-confirm is **app quit**, not Esc→launcher | `canon/ADR/001-one-tree-embedded-session.md:64-67` |
| Play chrome still placeholder (geometry/chrome later WO) | `tw2002_aiclient/screens.py:285` · `screens.py:295-296` |

---

## Test

`tests/test_play_esc_daemon_survival.py`

- `test_play_shell_esc_returns_back_not_quit` — Esc → `"back"`
- `test_run_play_source_never_calls_stop` — AST ban on stop/teardown names in `_run_play`
- `test_run_play_esc_issues_no_daemon_stop_verb` — stubbed `ensure_session`; spy on `session.cli.send_request`; Esc must leave wire empty (never touches `run/twd.sock`)

```bash
.venv/bin/python -m pytest tests/test_play_esc_daemon_survival.py -q
```

---

## Verify-vs-gap (honest)

| Accept criterion (PREP) | This lane |
|---|---|
| Esc → clean launcher return (`"back"`, not process exit) | **PASS** — `screens.py:354-355` + `app.py:151-152` + test |
| Esc must NOT tear down session (daemon-survival) | **PASS (structural)** — no stop verb / no teardown on Esc path |
| Layer-B pty + isolated FakeSession still-alive after Esc | **GAP** — not executed this lane. Play shell **does** call `ensure_session` on entry (`app.py:140`), but chrome is still the placeholder; there is no attach/subscribe binding to tear down on Esc. A stronger "daemon PID/sock still live after Esc" FakeSession e2e remains future proof once cockpit attach is wired — must still use isolated sock, never `run/twd.sock`. |
| Exit-confirm popup | **OUT OF SCOPE** (Phase 5 / N5) — correctly not present on Esc |

**Bottom line:** today's Esc path cannot kill the daemon because it never asks to. That is the ADR-001 survival property for Esc→launcher. Claiming a live-session survival e2e without a FakeSession harness would over-claim; this note does not.
