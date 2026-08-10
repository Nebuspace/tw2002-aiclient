# WO-CANON-DRAFT-WATCHFEED-CONCURRENT-START-STOP-CONTRACT

**Status:** IN FLIGHT · Cursor · `wo/CANON-DRAFT-WATCHFEED-CONCURRENT-START-STOP-CONTRACT`
**Seat:** `impl-aiclient-cursor`
**Depends:** `main` ≥ `e019ae7b` (#662 MERGED)
**Refs:** cycle-49 audit · `tw2002_aiclient/watchfeed.py` lifecycle docstring ·
`canon/surfaces/spectate-and-attach.md`

## Why

`WatchFeed`'s class docstring admitted that general concurrent `start()`/`stop()`
(beyond the mid-connect `stop()` race) was "undocumented territory." Canon
`spectate-and-attach.md` had no single-owner-thread contract note.

## Goal

Docs tip-true: make the single-owner-thread requirement an explicit canon
contract; point the product docstring at that note (no behavior change).

## Scope

1. `canon/surfaces/spectate-and-attach.md` — Code Divergence paragraph.
2. `tw2002_aiclient/watchfeed.py` — docstring only (cite canon; drop
   "undocumented territory").
3. This WO file.

## Out of scope

- Adding locks / making multi-thread `start()`/`stop()` safe.
- Changing `snapshot()` thread-safety or mid-connect `stop()` handling.
- Ops `tw watch` / WatchHub semantics.

## Accept

1. Canon states single-owner-thread for `WatchFeed.start`/`stop`.
2. Canon names the mid-connect `stop()` exception (WO-P4-050) without
   overselling it as a general concurrent contract.
3. Product docstring no longer claims the general case is undocumented.

## Proof

- Diff review of the two paths (+ this WO).
- `live-prove: n/a` (docs/contract comment only).
