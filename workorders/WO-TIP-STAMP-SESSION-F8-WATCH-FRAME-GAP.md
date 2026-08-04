# WO-TIP-STAMP-SESSION-F8-WATCH-FRAME-GAP

**Status:** DONE (pending merge) · stamp-correction only
**Priority:** LOW
**Gated:** no

## Goal

Flip stale BANKED marks for SESSION-F8 / MT-04 / A-L3-SESSION-F8 — product +
tests already on tip since `397f11d` / `WO-MT-04-WATCH-FRAME-SWALLOW`.

## Scope

- `canon/findings.md` SESSION-F8 → DONE
- `workorders/AUDIT-MISSING-TESTS.md` MT-04 → DONE
- `workorders/AUDIT-OKF-6LENS-BACKLOG.md` A-L3-SESSION-F8 → DONE
- This WO file

## Accept

1. Ledgers match tip `tw watch` unparseable-frame tell.
2. live-prove: `n/a` (docs stamp only).

## Proof

`pytest -k unparseable_frame` green; STATUS SHA.
