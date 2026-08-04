# WO-AUDIT-CANON-DRAFT-TEACH-BAND-CROSSREF

**Status:** DONE (pending merge) · `impl-aiclient-cursor`
**Priority:** LOW
**Depends-on:** none
**Gated:** no

## Goal

Cross-link mode-line calm-band vocabulary to tip token modules (`teachband`,
`autonomy_keys`, `reflex_controls`, `CHAINS_TOKEN`) so chrome and handlers cannot drift.

## Scope

- `canon/surfaces/mode-line-and-teach-controls.md`
- This WO file

## Accept

1. Canon names the tip modules + TOKEN symbols for calm band / reflex / loops.
2. Explicit "import TOKEN; do not re-type" drift rule.
3. live-prove: `n/a` (docs-only).

## Proof

`rg teachband|REFLEX_TOKEN|autonomy_keys canon/surfaces/mode-line-and-teach-controls.md` + STATUS SHA.

## Refs

- queue-aiclient.md `AUDIT-CANON-DRAFT-TEACH-BAND-CROSSREF`
- `tw2002_aiclient/cockpit/{teachband,autonomy_keys,reflex_controls,chains}.py`
