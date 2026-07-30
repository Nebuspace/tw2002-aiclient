# WO-ENSURE-STALE-SOCK-RECOVER — orphan `twd.sock` makes ensure `spawn_failed`

**Status:** DONE · origin `26b13e4` (#210) · Accept verified 2026-07-30
**Seat:** Cursor (`impl-aiclient-cursor`) · Live: brief smoke ensure OK
**Refs:** Max Play ensure · hub repro · `session/cli.py` `ensure_raw` · `daemon.py` stale-sock comment

## Finding (reproduced)

When `twd.sock` exists but no daemon is alive (crashed / killed / leftover live-prove):

1. `ensure_raw` sees `not (alive and sock)` → spawn path.
2. Wait loop `while not sock_path.exists()` exits **immediately** on the orphan node.
3. New daemon’s preflight `bind` hits **EADDRINUSE** (or races); settle `read` against a dead/refusing sock fails for the whole timeout.
4. Operator sees: `spawn_failed: daemon socket present but never answered a round trip after Ns`.

Hub planted an orphan AF_UNIX node with no listener → exact detail string in 8s.

Daemon `main()` already unlinks stale sock **after** pidfile claim; **ensure never clears the orphan before treating file presence as readiness.**

## Accept

1. Before spawn (when daemon not alive): **unlink** `twd.sock` if present (and do not treat orphan presence as ready).
2. Pin: orphan sock + no pid → ensure still spawns a live daemon (or fails for a real connect reason), **never** the “socket present but never answered” detail caused solely by the orphan.
3. Mutation: skip the unlink → orphan repro goes red again.
4. Do not weaken single-connection / pidfile guards.
5. Suite green · smoke: `./tw ensure --profile <scout> …` after planting orphan sock succeeds past spawn (or honest remote fail) — STATUS notes.

## Constraints

Public-safe. Tiny diff — prefer `cli.ensure_raw` (+ maybe shared helper). No combat/dock invent.
