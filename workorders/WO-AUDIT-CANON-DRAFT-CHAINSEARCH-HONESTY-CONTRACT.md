# WO-AUDIT-CANON-DRAFT-CHAINSEARCH-HONESTY-CONTRACT

**Status:** DONE (pending merge) · `impl-aiclient-cursor`
**Priority:** LOW
**Depends-on:** none
**Gated:** no

## Goal

Canon-pin `chain_search_view.py`'s partial-listing honesty (PARTIAL banner;
truncated-empty ≠ absence) and its separation from the recorded-macro ARM list.

## Scope

- `canon/ADR/003-discovered-chain-approve-scaffold.md`
- `canon/surfaces/mode-line-and-teach-controls.md` (L)chains bullet)
- This WO file

## Accept

1. ADR-003 + mode-line name the tip formatter and truncation rules.
2. Explicit "do not blur with ARM rows" tripwire.
3. live-prove: `n/a` (docs-only).

## Proof

`rg chain_search_view|PARTIAL_|part searched` on the two canon files + STATUS SHA.

## Refs

- queue-aiclient.md `AUDIT-CANON-DRAFT-CHAINSEARCH-HONESTY-CONTRACT`
- `tw2002_aiclient/chain_search_view.py`
