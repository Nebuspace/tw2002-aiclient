# WO-RUN-DIR-AFUNIX-REFUSE — Honest refuse when TW_RUN_DIR socket path too long

**Status:** OPEN · EXECUTE · MED · Cursor-class · impl-aiclient-cursor  
**Posted:** 2026-07-27T21:56:00Z · CC finding during autoloop_start live matrix  
**Seat:** impl-aiclient-cursor · EXEC seeded 2026-07-28T02:29Z (IDLE-KICK feed; FRESHNESS-SWEEP still HOLD until #128 twin on main)  
**Refs:** #116 transport prove · WO-RUN-DIR-NORMALISE (E-01) class

## Goal
When `TW_RUN_DIR` yields an AF_UNIX path over the OS limit (~104 on macOS), `twd` must **refuse with a named error mentioning the run dir / path length** — not die with an unhandled `OSError` traceback at `server_bind`.

## Accept
1. Over-long run-dir → named refusal (no raw traceback to operator).
2. Unit/integration pin that forces the long-path case and asserts the named refusal.
3. Suite + STATUS; live-prove n/a (daemon bind edge) unless easy to prove in matrix.

## Constraints
No change to happy-path run-dir layout beyond the refuse path. Public-repo safe (no secrets).
