# WO-ENSURE-SPAWN-READINESS

**Status:** OPEN · product (`session/cli.py`) · Claude Code lane · banked 2026-07-26
**Posted:** 2026-07-26 · root-caused from the live ensure matrix (2 of 5 cells)

## Scope correction vs the banking request

The hub banked this as *"`empty_response` **after stop→re-ensure**"*. **That framing is too narrow and a fix built to it would leave half the defect standing.** The hub's own outcomes table records `game.a-net-online.lol`'s **first** ensure — before any stop — as `empty_response`. Observed both ways:

```
twgs.microblaster.net : ensure -> real stall (step 6)    | stop + re-ensure -> empty_response
game.a-net-online.lol : ensure -> empty_response         | stop + re-ensure -> real stall (step 5)
```

**Two hosts, opposite orders, same symptom.** The common factor is a **freshly spawned daemon**, not a preceding stop. Scope is spawn readiness generally.

## Goal

`ensure` must not report `empty_response` because it spoke to a daemon that had not finished starting. Prove readiness by a **successful round trip**, never by a path existing.

## Root cause (verified at tip `ca8108a` — re-verify, do not trust this)

Two defects, one line apart in `tw2002_aiclient/session/cli.py`:

1. **`:269-272`** — readiness is proven by a filesystem check:
   ```python
   while time.monotonic() < spawn_deadline and not sock_path.exists():
       time.sleep(0.1)
   ```
   A unix socket file exists before anything is accepting on it. This is the `Path.exists()`-collapse
   pattern this codebase has been bitten by repeatedly: **presence of a path is not readiness of the
   thing behind it.**

2. **`:283`** — the probe that *would* have caught it **runs and its answer is discarded**:
   ```python
   send_request("read", {...}, timeout=settle_budget + 5, run_dir=run_dir)
   ```
   No assignment, no check. If this returns `{"ok": False, "error": "empty_response"}` — precisely
   the not-ready signal — nothing reads it, and execution falls through to the real ensure which
   meets the same unready daemon.

**The defect is not a missing readiness probe. It is a readiness probe whose result nobody reads** —
the same shape as a floor that is accepted and never checked. The right action is already performed;
only the evidence is dropped.

## Why it matters beyond a flake

`empty_response` maps to `REASON_CONNECT_FAILED` (`adapters.py:40`) — a **local** condition. Left as
is, it lands in operator-facing results as though a **third-party server** failed. The live matrix
produced exactly that: two hosts carrying an `empty_response` row that says nothing about them.
**A false claim about someone else's service, and a real defect of ours buried underneath it.**

## Scope

- `tw2002_aiclient/session/cli.py` — the spawn/readiness path only.
- Tests as needed.
- **Not** the login automaton, not `protocol.py`, not the daemon itself.

## Constraints

- **Do not extend the overall ensure budget.** Readiness polling must live *inside* the existing
  deadline — a fix that makes a failing ensure take longer to fail is not an improvement.
- Preserve the distinction between "daemon never came up" (`spawn_failed`) and "daemon came up but
  was not answering yet". Collapsing them re-creates the same class of lie in a new place.
- `empty_response` must remain reachable for the genuine case (a daemon that really does close
  without answering) — this WO removes a false cause, not a real signal.
- No new external dependencies.

## Accept

A freshly spawned daemon is not driven until a round trip has actually succeeded, or the budget
expires with a **distinguishable** error. `empty_response` is no longer reachable purely because the
client was faster than daemon startup.

## Required injection

Restore the discarded-probe behavior (ignore the `read` result, keep the `Path.exists()` wait) and
prove a test goes **red**. If nothing fails, the pin has not been built. A timing defect is easy to
"fix" in a way that only makes it rarer — **the test must fail deterministically, not statistically**;
prefer a fake whose first N requests return zero bytes over a sleep-based race.

## Proof

STATUS + SHA · the injection result · full-suite count from junitxml read after process exit
(baseline **3373**) · tree md5 fingerprint bracketing the certification run.

## Refs

Live matrix cells 2026-07-26 (`impl-aiclient-cursor`) · hub taxonomy 09:38:38Z ·
`adapters.py:40` (`empty_response` → `REASON_CONNECT_FAILED`) · CC root-cause post 09:37:50Z
