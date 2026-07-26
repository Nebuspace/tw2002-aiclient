# WO-WEDGED-SEND-FENCE-STICKS

**Status:** READY FOR HUB COMMIT · Cursor · `wo/WEDGED-SEND-FENCE` · tip pending push  
**Posted:** 2026-07-26 · Cipher MEDIUM on `WO-CONTROL-LOCK-AUTOLOOP-FENCE`

## Fix landed (this tip)

- `TelnetConnection.force_unblock_sends()` — shutdown socket to wake blocked `sendall` (does **not** clear fences).
- `Session.send_raw` — after courtesy fence bound, if still fenced → force-unblock + short absorb wait.
- `AutoLoopRunner.stop` — after join timeout, force-unblock so `_run`'s `finally` can `leave_auto_loop`.
- Pins: `tests/test_wedged_send_fence.py`.

**Generation token:** preserves wedged predecessor fence (does not heal); see test + Accept note in the pin file.


## Goal

A wedged auto-loop send leaves the human's wind-down fence raised **permanently**, taxing every
subsequent keystroke by the full bound with no self-healing. Give the stuck case a way out.

## The mechanism (each link verified at tip, not inherited from the review)

1. `connection.py:132` — `self._sock.settimeout(None)`. **The telnet socket is blocking with no send
   timeout.**
2. `connection.py:219` — the module's *own* comment concedes a *"blocked `sendall()` is a real
   partial-transmission case, not a theoretical one."*
3. `session.py:49` — `_FENCE_WAIT_TIMEOUT_S = 10.0`, the per-call bound the human's attach path waits.
4. `_auto_loop_fenced` is cleared **only** by `leave_auto_loop()`, which fires **only** from
   `AutoLoopRunner._run`'s `finally`.

**So:** if the auto-loop thread is blocked inside `sendall()` when a human calls `take_human()`, the
fence is raised and the thread **never reaches its `finally`.** Nothing clears the fence for the life
of the process.

## Impact — annoying, not a control violation, and the distinction matters

The human's attach **never fails** and no single call hangs: `take_human()` still only ever raises
`already_attached`, and each `send_raw` wait is capped at 10s. **Control is never denied.**

But every keystroke pays the full 10s, in this attach session and every future one, until the process
restarts. **The operator's own keyboard becomes practically unusable.**

**The trigger is remote and untrusted:** a stalled or hostile TWGS peer that stops draining its receive
window mid-step. This project treats TWGS bytes as untrusted input by doctrine.

## Relationship to the fence WO

**This hazard is pre-existing** — the blocking socket predates the fence. **The fence amplifies it:**
before, a wedged auto-loop thread raised no fence at all, so the human paid nothing. Do **not** treat
this as a reason to revert the fence; the fence closes a real interleaving hazard.

Check whether the **generation token** added in the fence revision changes the severity — a fresh
generation may now be able to clear a wedged predecessor's fence, which would reduce this from
"permanent" to "until the next run starts".

## Scope

- `tw2002_aiclient/session/connection.py` — send-side timeout, and/or
- `tw2002_aiclient/session/autoloop.py` — a supervisory path that can mark a run crashed and release
  its hold/fence when its thread has not reached `finally` after a grace period.

## Constraints

- **Do not weaken the per-call bound into an unbounded wait.** The current 10s cap is what keeps this
  an annoyance rather than a denial; anything that removes it makes the bug worse.
- **A send timeout changes real wire behaviour.** A partial send on a blocking socket is already
  documented here as a live case — do not introduce a path that silently drops or duplicates bytes to
  the game. A truncated command is worse than a slow one.
- **Do not let a watchdog become a second driver.** Anything that force-releases a hold must not allow
  a new run to start while the wedged thread could still wake and write.
- No new external dependencies.

## Accept

A wedged auto-loop send no longer leaves the fence raised indefinitely; the human's keystroke latency
returns to normal without a process restart. Per-call bound preserved. No byte-level regression on the
partial-send path.

## Proof

STATUS + SHA · a deterministic test that wedges the send (a fake whose `sendall` blocks) and proves the
fence clears · full suite from junitxml after process exit · explicit statement of what the generation
token already covers.

## Refs

Cipher review of `WO-CONTROL-LOCK-AUTOLOOP-FENCE` 2026-07-26 · `connection.py:132,219` ·
`session.py:49` · hub bank 2026-07-26T13:31:12Z
