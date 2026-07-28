# WO-TEST-STATE-PARSER-REHAB — Rehabilitate ignored state-parser tests

**Status:** OPEN · EXECUTE · HIGH · Cursor (`impl-aiclient-cursor`)  
**Posted:** banked #149 · EXEC after #151 DELETE  
**Refs:** AUDIT-TEST-IGNORE-LIST-LANDMINE.md

## Goal
Rehab ignored state-parser test file(s) from the audit table onto in-tree APIs (no twclient).
Un-ignore when collect+pass, or DELETE if producer is gone (same #151 lesson — no stubs).

## Accept
1. Honest disposition: rehab+un-ignore or DELETE+drop ignore.
2. Leave import-hygiene vacuity pins untouched.
3. Suite green; live-prove n/a.

## Constraints
Cite audit row(s). Avoid #147 cockpit/chains. Explicit paths. No new deps.
