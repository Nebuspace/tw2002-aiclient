# WO-P3-030 — Play-chrome navigation (VERIFY)

> Status: **DONE** · origin `baa2779` (hub Accept stamp 2026-07-26 · was EXECUTE DONE awaiting Accept)
> Seat: `impl-aiclient-cursor` · verify-only · **no** Fable chrome (031–033)
> Depends: PREP `WO-P3-030-033-cockpit-frame-PREP.md` §PWO-030 · D1 harness `49b21a1`
> Out of scope: double-line frame / gutters / fold · exit-confirm popup (Phase 5 / N5)

---

## Goal

Prove Enter → play shell (handle visible) → Esc → clean launcher return (`"back"`, not process exit) with **ADR-001 daemon-survival** (Esc never tears down the session).

## Shipped

| Path | Role |
|------|------|
| `tests/test_play_chrome_nav.py` | Layer-B pty Esc↔launcher + unit Esc/`FakeSession` survival |
| `tests/test_play_esc_daemon_survival.py` | Structural AST + wire-spy: no `stop` on Esc |
| `WO-P3-030-daemon-survival-VERIFY.md` | Honest verify-vs-gap note for survival e2e |

**Product code:** no `screens.py` / `app.py` edits required — Accept already satisfied in substance (PREP).

## Accept → Proof

| Accept | Result |
|--------|--------|
| Enter → play shows handle | **PASS** Layer-B (`SELECT PROFILE` → Enter → `PLAY SHELL` + handle) |
| Esc → `"back"` → launcher; play chrome gone | **PASS** Layer-B + unit |
| Esc does not tear down daemon | **PASS (structural)** — no stop/teardown on Esc path; wire spy empty |
| Exit-confirm popup | **OUT OF SCOPE** (Phase 5) |

### Gap (banked, not blocking)

Live PID/sock “still alive after Esc” FakeSession e2e not claimed — play entry calls `ensure_session` but Esc has no attach/subscribe teardown to exercise. Stronger e2e later once cockpit attach is wired; still isolated sock only, never `run/twd.sock`.

## Proof commands

```bash
.venv/bin/python -m pytest tests/test_play_chrome_nav.py tests/test_play_esc_daemon_survival.py -q
scripts/path-leak-scan.sh
```

## Lane note for CC · Fable

`screens.py` PlayShellScreen **unchanged** this WO — chrome-wire for 031–033 may proceed after hub Accept / this seat’s 🛰️ HEADS-UP lane-clear.
