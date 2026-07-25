# WO-PATH-RELATIVIZE — Relativize absolute paths in workorder Proof commands

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`1d5dacb`** (CC)
> Type: docs/harden · Priority: P1 · Seat: impl-claudecode-aiclient
> Refs: `workorders/WO-P0-*.md` … `workorders/WO-P1-*.md` · path-leak hook

## Goal
Scan early WO Proof commands for absolute paths (e.g. `/Users/...`) that would fail on any other seat. Replace with relative commands. Applied alongside path-leak hook enforcement.

## Scope
- `workorders/WO-P0-*.md` + `workorders/WO-P1-*.md` — Proof command path relativization

## Outcome
Hub independent prove ✅ — tip `1d5dacb`. Scores: Completeness 98 / Quality 94 → SHIP.

## Refs
hub HANDOFF @ 00:50:50Z · hub verify ✅ `1d5dacb`
