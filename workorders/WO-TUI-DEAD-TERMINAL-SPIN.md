# WO-TUI-DEAD-TERMINAL-SPIN

**Status:** OPEN · **HIGH** · product + tests · from a live incident on the operator's laptop
**Posted:** 2026-07-26 · after 11 orphaned processes were found pegging ~11 of 16 cores

## Incident

Eleven orphaned Python processes, each at ~100% CPU (**~1094% total**), had been running for
**22h45m** and **7h05m** respectively. All were `curses.wrapper(_run)` — **the real product TUI** —
spawned by the cockpit PTY tests, orphaned to `PPID 1`, with their bootstrap scripts already deleted
from disk. Load average was `26.52` (15-min) on a 16-core machine.

Killed manually. This WO exists so it cannot recur.

## Defect 1 — PRODUCT: the TUI busy-spins on a dead terminal (this is the important one)

`tw2002_aiclient/app.py:316` sets `stdscr.timeout(1000)`, so `getch()` returns `-1` after ~1s of no
input. The loops at `:176-179` and `:335-338` treat `-1` as *"nothing typed, redraw and poll again"* —
correct at ~1 Hz.

**When the controlling pty goes away, `getch()` returns `-1` IMMEDIATELY rather than after 1s.** The
loop cannot tell the difference, so it reads a dead terminal as **an infinitely fast idle user** and
spins at 100% CPU forever.

**`-1` is one value standing in for two distinguishable states:** *"the 1s timeout elapsed"* and
*"the terminal is gone."* That is the same defect shape as `Path.exists()` conflating present-with-
ready (`WO-ENSURE-SPAWN-READINESS`) and a single slot standing in for a set
(`WO-CONTROL-LOCK-AUTOLOOP-FENCE`).

**This is NOT only a test problem.** Any real operator whose terminal dies — ssh drop, closed window,
killed tmux — leaves the product spinning a core on their machine. **It is an operator-facing bug that
the tests merely reproduced eleven times over.**

### Fix direction (argue it, do not assume)

Distinguish the two states. Candidates:

- **Timing:** with a 1000 ms timeout, N consecutive `-1`s arriving in far less than N seconds means
  the terminal is gone, not idle. Cheap, portable, no new syscalls.
- **Orphan self-defence:** `os.getppid() == 1` → our parent died; exit cleanly. (macOS has no
  `PR_SET_PDEATHSIG`, so a poll is the portable equivalent.)
- **Explicit EOF/error detection** on the input fd.

**Whatever is chosen, exit CLEANLY** — release the control lock, restore the terminal, do not leave a
half-torn-down curses state. **Do not fix this by lengthening the timeout**; that makes the spin
slower, not absent.

## Defect 2 — TESTS: orphans survive a hard kill of pytest

`tests/pty_helpers.py` and ~10 `test_cockpit_*_pty.py` files spawn with **`start_new_session=True`** —
deliberate and correct (it stops the child claiming the runner's controlling terminal), and documented
as such. But it also puts the child in **its own session and process group**, so it is not reached by a
kill of pytest's group.

Cleanup lives in a `finally:` that calls `proc.kill()`. Correct on every normal exit **including test
failure** — but **a SIGTERM to pytest skips `finally` entirely** (Python's default handling terminates
without unwinding). Result: child survives, orphans to init, and — because of Defect 1 — spins.

**Known trigger, and it is ours:** a full-suite run that exceeds a shell/tool timeout gets SIGTERM'd.
That happened in this session (`exit code 143`), was noticed only as "the command timed out", re-run
with a longer limit, and the orphans were never looked for.

### Fix direction

- **`os.killpg(os.getpgid(proc.pid), SIGKILL)`** in the `finally` rather than `proc.kill()` — reaps the
  whole session including anything the child spawned. Keep `start_new_session=True`; it is right.
- Consider a **session-scoped autouse fixture** that reaps any surviving bootstrap at session end, as a
  second layer for the ordinary (non-hard-kill) path.
- **Neither survives SIGKILL of pytest** — that is what the external sweep in the protocol amendment is
  for. Do not pretend an in-process fix closes the hard-kill case.

## Scope

- `tw2002_aiclient/app.py` — the input loops (Defect 1).
- `tests/pty_helpers.py` + the `test_cockpit_*_pty.py` spawn sites (Defect 2).
- **Not** the coordination scripts — the sweep is a separate protocol amendment.

## Constraints

- **Do not remove `start_new_session=True`.** Its isolation purpose is real and documented.
- **Do not lengthen the getch timeout as the fix.** A slower spin is still a spin.
- **Do not exit on a single `-1`** — that is the normal idle path and would break every TUI test and
  the product's own 1 Hz refresh.
- Clean teardown: control lock released, terminal restored.

## Accept

A TUI whose terminal is taken away **exits promptly and cleanly instead of spinning**, proven by a test
that closes the pty master and asserts the child exits within a bounded time **and** that its CPU time
does not grow. Orphan-on-hard-kill no longer leaves a running process for the ordinary paths.

## Proof

STATUS + SHA · a test that kills the pty master and measures both **exit** and **CPU time consumed** ·
full suite from junitxml after process exit · **a before/after `ps` showing zero orphans after a
deliberately SIGTERM'd suite run**.

## Refs

Live incident 2026-07-26 (11 procs, ~1094% CPU, 22h45m + 7h05m) · `app.py:176,316,335` ·
`tests/pty_helpers.py:183,203,257,276` · companion protocol amendment: orphan sweep
