# WO-P2-OPS-VERB-A — tw screen + tw stop (CLI wire, slice A)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tips **`7041cdf`** + **`ba3e250`** (Cursor)
> Type: build · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-P2-OPS-VERB-SURFACE.md` slice A · `canon/surfaces/spectate-and-attach.md`

## Goal
Wire CLI `tw screen` + `tw stop` (protocol already present) — slice A of the ops verb surface. README Verb reference moves `screen`/`stop` from Coming → shipped.

## Scope
- `tw2002_aiclient/session/cli.py` (+ thin helpers if needed)
- `tests/` FakeSession/isolated run-dir for both verbs
- `README.md` Verb reference update
- `workorders/WO-P2-OPS-VERB-SURFACE.md` slice-A tick

## Constraints
- No screens/cockpit; no `do`/`send` yet; no new deps
- Path-leak green; push waits Accept
- Full `pytest tests/` green

## Accept
1. Both `screen` and `stop` on `./tw --help`
2. Unit/FakeSession proof for each
3. README Verb reference updated same commit

## Proof
`./tw --help` + `pytest` for the verbs + full suite. Hub Completeness 92 / Quality 91 → SHIP (tips `7041cdf` + `ba3e250`).

## Refs
`WO-P2-OPS-VERB-SURFACE.md` slice A · `session/protocol.py` · hub Accept + Push GO @ 12:28:35Z + 12:29:17Z
