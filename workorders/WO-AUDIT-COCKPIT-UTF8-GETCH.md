# WO-AUDIT-COCKPIT-UTF8-GETCH — Cockpit getch() UTF-8 decode under ruled UTF-8 contract

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **HANDOFF'd** 2026-07-25 · dispatched to Cursor in wave @ 13:29:19Z · in-flight (queued behind TEST-AUDIT as Max-priority)
> Type: harden · Priority: P1 · Lens: L2 code-vs-canon / UTF-8 contract
> Refs: `tw2002_aiclient/` cockpit/app.py getch path · `canon/surfaces/visual-language.md` UTF-8 contract

## Goal
Verify cockpit `getch()` correctly decodes multi-byte UTF-8 sequences under the ruled UTF-8 contract. `app.py` owns the getch path — confirmed free of CC live lanes (G3/SURROGATE on `cli.py`/`loops/`). Ruled UTF-8 contract is the canon governing what the cockpit keyboard reader must handle.

## Scope
- `tw2002_aiclient/app.py` / `cockpit/` — getch path; UTF-8 multi-byte decode
- `tests/` — UTF-8 multi-byte keystroke layer (pure / pty)

## Constraints
- No fighting CC live lanes (G3/SURROGATE in `cli.py`/`loops/`)
- Ruled UTF-8 contract: no invented encoding rules
- Full suite green; path-leak

## Accept
1. Cockpit getch correctly handles multi-byte UTF-8 sequences per ruled contract
2. No crash / silent-drop on valid UTF-8
3. Full suite green

## Proof
UTF-8 keystroke unit test + optional pty; STATUS + SHA; Push waits Accept.

## Refs
hub HANDOFF wave @ 13:29:19Z · `visual-language.md` UTF-8 contract · `app.py` getch
