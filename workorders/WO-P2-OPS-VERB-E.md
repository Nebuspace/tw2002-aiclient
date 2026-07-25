# WO-P2-OPS-VERB-E — tw watch inventory (docs-only; WatchHub substrate needed)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE (docs-only)** 2026-07-24 · tip **`78bb983`** (Cursor)
> Type: docs/deferred · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-P2-OPS-VERB-SURFACE.md` slice E · `canon/surfaces/spectate-and-attach.md`

## Goal
Inventory + honesty-or-wire `tw watch` (settle-edge / WatchHub event stream). Outcome: docs-only — WatchHub substrate (`watch.py` + daemon `_handle_subscribe`) not yet ported. README/WO marks watch deferred. `./tw --help` unchanged; no fake streaming verb.

## Scope
- `workorders/WO-P2-OPS-VERB-SURFACE.md` slice-E note (WatchHub missing; deferred to E2 after substrate)
- README honest note

## Constraints
- Do not invent a fake streaming verb without a hub
- No screens/cockpit

## Accept
- STATUS cites missing `WatchHub`/`watch.py`; README/WO mark watch deferred; `./tw --help` unchanged; no fake verb
- Hub Accept confirms docs-only path correct; E2 follows after WATCHHUB-PORT substrate

## Proof
STATUS + SHA (docs only). WATCHHUB-PORT substrate follows immediately.

## Refs
`WO-P2-OPS-VERB-SURFACE.md` slice E · `spectate-and-attach.md` WatchHub · hub Accept + Push GO @ 14:19:34Z
