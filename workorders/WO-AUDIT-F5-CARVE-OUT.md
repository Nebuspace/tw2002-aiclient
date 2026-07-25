# WO-AUDIT-F5-CARVE-OUT — Session audit F5: daemon broad-except wire leak (carve-out investigation)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **PARKED / SUPERSEDED** · F5-B product wire PARKED (Max: no carve-out comment) · **Superseded by WO-AUDIT-F5-TYPE-NAME** (Max GO @ 10:27 ET: F5→A, type-name-only on wire)
> Type: harden/audit · Priority: P0 · Lens: L2 code-vs-canon / info-leak
> Refs: `tw2002_aiclient/session/daemon.py` `:76-77` · `guardian.py:161` · `canon/architecture/secrets-and-credentials.md`

## Goal
Investigate whether a carve-out comment in `daemon.py` for the widest `except Exception` branch (potential path/args leak on wire) was warranted. Finding: F5-B product wire needs type-name-only, NOT a carve-out comment. `guardian.py:161` NARROW catch (`except (OSError, LoginError)`) keeps full `str(e)` — correct per doctrine (narrow catch knows provenance). Carve-out comment = NOT written (correctly).

## Scope (investigation only)
- `tw2002_aiclient/session/daemon.py` `:76-77` — broad `except Exception` wire path
- `tw2002_aiclient/session/guardian.py:161` — narrow catch (carve-out scope)

## Constraints
- No product change in this WO; investigation and ruling only
- Product wire: WO-AUDIT-F5-TYPE-NAME handles the fix
- `guardian.py:161` narrow catch = out of scope for type-name rule

## Verdict / Outcome
F5-B product wire PARKED (hub ACK @ 14:23:36Z — no carve-out comment written; `daemon.py` stays untouched). Escalated to Max @ 10:27 ET: F5→A (type-name-only + local traceback WO). **WO-AUDIT-F5-TYPE-NAME is the live execution WO.**

## Refs
hub HANDOFF @ 13:13:55Z · F5-B STOP / carve-out PARKED @ 14:23:36Z · Max re-rule @ 10:27 ET → WO-AUDIT-F5-TYPE-NAME
