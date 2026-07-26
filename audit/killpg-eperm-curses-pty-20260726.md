# killpg → EPERM on curses-in-pty teardown (WO-TUI-KILLPG-EPERM-CURSES-PTY)

**WO:** `WO-TUI-KILLPG-EPERM-CURSES-PTY`  
**Seat:** `impl-aiclient-cursor` · branch `wo/TUI-KILLPG-EPERM-CURSES-PTY` · PR #18  
**Date:** 2026-07-26  
**Depends:** `WO-TUI-DEAD-TERMINAL-SPIN` on main (`terminate_session_group` + loud EPERM warn)

No secrets in this file.

---

## Banked evidence (opened, not rediscovered)

| Observation | Status |
|---|---|
| ~88 `PermissionError` warnings per full suite when curses-in-pty teardown calls `os.killpg` | Banked (CC cert machine) |
| Plain `sleep` child, identical `start_new_session=True` / pty shape | **0** EPERM — sleep negative fixture was structurally blind |
| Reproduces under `-n0` and `-n auto` | Banked |
| Measured orphan leak today | **None** when the curses child holds no live grandchild at teardown |
| Latent risk | Present **if** a curses-in-pty child still holds a live grandchild (`twd`, etc.) when EPERM fires — group sweep degrades to direct-child kill |

Source: WO body + CC STATUS 18:00:47Z / CORRECTION 18:02:30Z (do not re-derive).

---

## Root cause (bounded)

**Named shape:** `terminate_session_group` → `os.killpg(proc.pid, SIGKILL)` against a session/process-group leader that is (or was) a **curses-in-pty** child spawned with `start_new_session=True` (no `TIOCSCTTY`) reliably raises **`PermissionError` (EPERM)** on the cert Darwin environment.

**What it is not:**
- Not mid-suite flake alone (reproduces serial and parallel).
- Not “killpg never works for setsid children” — the sleep control proves setsid+pty alone is insufficient to trigger EPERM.
- Not fixed by removing `start_new_session=True` (forbidden — isolation purpose is load-bearing for WO-P3-PTY-CTTY / orphan incident).

**Kernel/curses mechanism:** **not fully isolated.** Candidates (unproven): Darwin session-leader / signaling interaction with a process that has initialized ncurses against a pty slave; timing around leader exit vs group membership. This tip does **not** claim a single ioctl or flag as the cause.

**Honesty correction vs prior helper comment:** an earlier note framed EPERM as “intermittent in one sandboxed environment, not reproduced elsewhere.” Suite-scale curses-in-pty evidence contradicts that framing — treat EPERM as a **known platform carve-out for this spawn shape**, not a rare sandbox glitch.

---

## Product response this tip (carve-out, not overclaim)

Keep current behaviour in `tests/pty_helpers.terminate_session_group`:

1. Prefer `os.killpg(proc.pid, SIGKILL)` when the child is (or was) a setsid leader.
2. On `PermissionError`: **loud** `RuntimeWarning` (must not go silent) + fall back to `proc.kill()` (direct child only).
3. Docstring / warn text must **not** claim unconditional “reaps the whole group” — the EPERM path explicitly does **not**.

No change to `session/login.py`. No invent screen classes. No expansion of dead-terminal spin product beyond existing merge.

---

## Pins

- Injected `PermissionError` on `os.killpg` → warning emitted + direct child terminated (EPERM path stays loud).
- Existing curses-in-pty dead-terminal tests still prove prompt exit without hang (`tests/test_dead_terminal_spin.py`).

---

## Accept claim

1. This audit note = root-cause / bounded unknown with recipe.  
2. Documented carve-out — no whole-group overclaim.  
3. Pins as above.
