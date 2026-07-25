# WO-AUDIT-LEGACY-WO-INDEX — WO-00…17 vs ULTRACODE map honesty

> Status: **EXECUTED** 2026-07-25 · AUDIT-OKF-6LENS docs tick · README live-queue banner tightened  
> Type: docs · Priority: P2 · Lens: L4 cleanup  
> Refs: `ULTRACODE-WO-INVENTORY.md` §Mapping · `workorders/WO-00`…`WO-17`

## Goal
Prevent operators/agents from treating rebirth `WO-00…17` stubs as the live execute queue; point clearly at ULTRACODE PWO-* + Phase PREPs.

## Scope
- A: `workorders/README.md` — banner: live queue = ULTRACODE / Phase PREPs; WO-00…17 = historical map only
- B: Optional one-line Status on each WO-0x header if missing “SUPERSEDED / mapped to PWO-…”
- C: Do not delete files in this WO (history); mark only

## Constraints
Docs-only. No renames that break external links without hub GO.

## Accept
README states single live queue; `rg` “execute WO-0” noise reduced by explicit superseded language.

## Proof
Docs commit. Push waits Accept.

## Refs
ULTRACODE §5 Mapping · `workorders/README.md`
