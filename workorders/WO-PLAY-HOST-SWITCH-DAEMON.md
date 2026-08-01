# WO-PLAY-HOST-SWITCH-DAEMON

**Status:** READY · EXECUTE · CRITICAL · Max live 2026-08-01 · Cursor  
**Seat:** `impl-aiclient-cursor`  
**Branch:** `wo/PLAY-HOST-SWITCH-DAEMON`  
**Depends:** `main` ≥ `ad0aff8`

## Why (live · hub verified)

After escape-pod death on **exiled**, Max quit Play and tried **three other servers**. Viewport still looked like game select; login never progressed.

Hub `./tw status --json` while “stuck”:
- `daemon_running: true`
- `host: "twgs.exiled.org"` (still)
- `connected: false`
- `classification: "game_select"` (stale paint)

Esc Play does **not** stop the daemon (ADR-001). Play `ensure` **reuses** the live daemon and refuses other profiles with `profile_host_mismatch` — operator sees old game-select chrome and thinks “can’t get past game select on any server.”

Hub ran `./tw stop` as immediate relief (daemon down). Product must not require hub/operator CLI.

## Goal

When Play/ensure targets a profile whose host/port ≠ the running daemon’s session identity, **automatically stop (or retarget) and spawn** a daemon for the selected profile, then ensure — so switching servers from the launcher Just Works.

## Scope

1. **Detect** `profile_host_mismatch` / `profile_port_mismatch` (or pre-check identity before ensure) on Play entry / `ensure_session`.
2. **Recover:** stop daemon in that run_dir → spawn for the selected profile’s host/port → ensure to `main_command` (existing spawn path). Honest LOGS/status if stop/spawn fails.
3. Pins: fake/mismatch → stop+respawn invoked (or equivalent); happy same-host path unchanged.
4. Optional small: if `connected=false` and classification stuck `game_select` on old host, same retarget. Do not weaken game_select once-per-connection on a **live same-host** door (separate death-respawn WO).
5. This WO on the branch.

## Out of scope

#307 avoid→N REVISE (park until this unblocks Max) · #308 death new-char · changing Esc-to-kill-daemon default globally without Play host-switch.

## Accept

1. With daemon on host A, Play/ensure profile for host B succeeds (new daemon on B) without manual `tw stop`.
2. Same-host ensure unchanged; suite green.
3. Live-prove: hub/Cursor can show stop was needed on exiled wedged state (already) + optional multi-host ensure; else honest NOT-ATTEMPTED after offline pins.

## Proof

pytest + STATUS. No self-merge.

## Refs

Max 2026-08-01 · hub status dump exiled · `protocol._session_identity_mismatch` · `cli.ensure_raw` spawn-if-dead only · ADR-001 Esc leaves daemon
