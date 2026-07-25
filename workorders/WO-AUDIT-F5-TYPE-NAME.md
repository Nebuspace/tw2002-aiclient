# WO-AUDIT-F5-TYPE-NAME — Daemon widest catch: type-name-only on wire + local traceback log

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **DONE (local / push waits Accept)** 2026-07-25 · tip **`84947be`** · dispatched CC daemon-lane, executed and committed
> Type: harden · Priority: P0 · Lens: L2 code-vs-canon / info-leak
> Refs: `tw2002_aiclient/session/daemon.py` `:76-77` · `canon/architecture/secrets-and-credentials.md` · F5 CC audit finding

## Goal
Align widest daemon `except Exception` catch to type-name-only on the wire (`f"internal_error:{type(e).__name__}"` only — never `str(e)` / paths / args echoes). Keep full diagnostics via **local traceback log** (not wire). F5-B product wire (ACL/socket endpoint) **PARKED** — this WO is A only: wire-side type-name + local log.

## Scope
- `tw2002_aiclient/session/daemon.py` — `except Exception` path at `:76-77`; optional thin logger helper
- `tests/` — path-disclosure probe red→green (type-name on wire, visible in local log)

## Constraints
- Do NOT touch socket ACL here (separate WO-AUDIT-DAEMON-SOCKET-MODE)
- Narrow catches (`guardian.py:161` `except (OSError, LoginError)`) keep full `str(e)` — rule is unbounded→type-name, narrow→full text OK
- Secrets still UNVERIFIED coincidence — do not claim "safe" in STATUS
- Serialize: F5-A first, then socket-mode (single lane owns `daemon.py` end-to-end)
- F5-A + local-traceback are ONE obligation (not two): wire loses detail BECAUSE local log gains it; split = a diagnostic regression in between

## Accept
1. `except Exception` path returns `internal_error:{type(e).__name__}` only — never `str(e)` / path / args
2. Full traceback (or exception+stack) logged **locally** (stderr and/or run-dir log)
3. Path-disclosure probe that was VERIFIED red is green on wire (type name only) AND visible in local log
4. Narrow catches untouched (not "aligned")
5. Socket ACL deferred

## Proof
Reproduce path-disclosure probe red/green; STATUS + SHA; Push waits Accept.

## Refs
Max GO @ 10:27 ET · CC F5 premise-fail @ 14:23Z · hub HANDOFF @ 14:28:55Z · `daemon.py:76-77`
