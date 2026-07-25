# WO-AUDIT-DAEMON-SOCKET-MODE — Daemon listen socket owner-only mode (0o600)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **DONE (local / push waits Accept)** 2026-07-25 · tip **`bef97e1`** · executed and committed after F5-A (`84947be`)
> Type: harden · Priority: P0 · Lens: L2 code-vs-canon / access-control
> Refs: `tw2002_aiclient/session/daemon.py` socket bind/listen · `canon/architecture/secrets-and-credentials.md` `0o600` precedent · Max GO

## Goal
Daemon listen socket must not inherit a group/world-writable umask — force owner-only connect by default. After bind/listen (or at create), socket mode is **`0o600`** (or equivalent owner-only) — re-asserted, not umask-dependent. Phase 2 (peer uid / SO_PEERCRED) is OUT unless proven a one-liner with zero design fork.

## Scope
- `tw2002_aiclient/session/daemon.py` — socket bind/listen path
- `tests/` — umask matrix red→green; mode bits proven (`0o600`); group/other cannot connect

## Constraints
- **Safety list** — access-control; stay in scope; STOP+REPORT if design fork (e.g. multi-user shared daemon) appears
- Phase-2 peer-auth = follow-on WO only
- Serialize: after F5-A (single lane owns `daemon.py`)
- Pidfile policy unchanged unless required for consistency

## Accept (phase 1 — mode only)
1. After bind/listen, socket mode is `0o600` (or equivalent owner-only) — re-asserted, not umask-dependent
2. Under umask `0o000` / `0o002` probes, group/other cannot connect (or mode bits prove it)
3. Pidfile policy unchanged unless required

## Proof
Umask matrix red→green; STATUS + SHA; Push waits Accept.

## Refs
Max GO @ 10:27 ET · CC measurements @ 14:23Z · `secrets-and-credentials.md` `0o600` precedent · hub HANDOFF @ 14:28:55Z
