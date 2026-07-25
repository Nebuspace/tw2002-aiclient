# WO-P2-OPS-VERB-C — tw history (+ tw state deferred) (slice C)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`82b4094`** (Cursor) · `tw state` deferred (needs state_parser)
> Type: build · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-P2-OPS-VERB-SURFACE.md` slice C

## Goal
Wire `tw history` from live session ring (slice C). `tw state` only if a thin honest skeleton is feasible without a full `state_parser` port — else inventory + bank for later. Redaction on history (secrets never in output).

## Scope
- `tw2002_aiclient/session/cli.py`
- `tests/` FakeSession history proof
- README Verb reference + allowlist
- `WO-P2-OPS-VERB-SURFACE.md` slice-C tick

## Constraints
- No screens/cockpit; no new deps; path-leak; full suite green
- `tw state` deferred if state_parser not available: STATUS disclosure + WO note

## Accept
1. `history` on `./tw --help` + FakeSession proof
2. `state` shipped or explicitly deferred with STATUS disclosure
3. README/allowlist honest; full pytest green

## Proof
help + targeted + full suite. `state` honestly deferred with note.

## Refs
`WO-P2-OPS-VERB-SURFACE.md` slice C · hub Accept + Push GO @ 13:44:22Z
