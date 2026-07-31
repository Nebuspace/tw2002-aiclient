# WO-EXPLORE-DOCK-NEW-PORT — Dock newly found ports for commodity ingest during explore

**Status:** DONE · origin `fdcbd1c` (#205) · tip-honesty stamp 2026-07-31 (product on main; banner was stale OPEN)
**Posted:** 2026-07-28T22:36Z · Max GO — immediate data gathering on first sight  
**Refs:** flyby `port.class` (E2) · `write_port_only` / commodities · explore map-fill

## Goal

When explore first observes a **new** port (sector with a `Ports :` class triple not yet in the world model, or class present but `commodities` absent), **dock**, ingest the commerce-report commodity list into the world model, then undock/continue map-fill. Turn-spend is intentional (Max sacrificial / explore budget).

## Accept

1. First-sight (or class-without-commodities) triggers a dock+ingest path; already-complete ports are not re-docked every hop.
2. `port.commodities` populated from the docked report via existing writer (`write_port_only` or equivalent) — product caller, not tests-only.
3. Fail closed: unrecognized dock UI ⇒ typed halt / STOP explore (no silent wander). Confirm-gated if Play-arm requires it; CLI explore may use explicit explore intent flag.
4. Pins: no dock on `Ports : None`; no invent commodities; suite + STATUS.
5. live-prove: DEFERRED → Cursor (diversity) after offline green.

## Constraints

NPC/toll screens mid-dock ⇒ STOP. No Pay. Money-path adjacent — mack/cipher glance. Disjoint from combat EXEC paths where possible.
