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
| ~88 `PermissionError` warnings per full suite when curses-in-pty teardown calls `os.killpg` | Banked (CC cert machine) — **in this suite’s harness** |
| Plain `sleep` child, identical `start_new_session=True` / pty shape | **0** EPERM — sleep negative fixture was structurally blind |
| Minimal curses-in-pty + `start_new_session` alone (CC 18:42Z) | **0/3** EPERM — further harness ingredient required (unidentified) |
| Reproduces under `-n0` and `-n auto` | Banked (in-suite) |
| Measured orphan leak today | **None** when the curses child holds no live grandchild at teardown |
| Latent risk | Present **if** a curses-in-pty child still holds a live grandchild (`twd`, etc.) when EPERM fires — group sweep degrades to direct-child kill |

Source: WO body + CC STATUS 18:00:47Z / CORRECTION 18:02:30Z (do not re-derive).

---

## Root cause (bounded)

**Named shape (suite harness):** `terminate_session_group` → `os.killpg(proc.pid, SIGKILL)` against session/process-group leaders from **this suite’s curses-in-pty harness** (`start_new_session=True`, typically via `capture_pty*` / `_spawn_bootstrap`) reliably raises **`PermissionError` (EPERM)** on the cert Darwin environment (~88 warnings/suite).

**Not reproducible from curses-in-pty + `start_new_session` alone:** CC independent check (2026-07-26T18:42Z) — minimal curses-in-pty + setsid spawn, 0/3 EPERM; group sweep reaped the grandchild each time. So **suite harness has a further unidentified ingredient** beyond “curses + setsid” (candidates: `claim_ctty` / `set_winsize` / fd layout in bootstrap helpers — not isolated this tip).

**What it is not:**
- Not mid-suite flake alone (reproduces serial and parallel in-suite).
- Not “killpg never works for setsid children” — sleep controls and CC’s minimal curses repro both get clean group sweeps.
- Not fixed by removing `start_new_session=True` (forbidden — isolation purpose is load-bearing for WO-P3-PTY-CTTY / orphan incident).

**Kernel/curses mechanism:** **not fully isolated.** This tip does **not** claim a single ioctl or flag as the cause.

**Honesty correction vs prior helper comment:** an earlier note framed EPERM as “intermittent in one sandboxed environment.” In-suite volume contradicts that — treat EPERM as a **known carve-out for this suite’s pty harness shape**, not a rare sandbox glitch, and **not** as a universal curses+setsid law.

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
