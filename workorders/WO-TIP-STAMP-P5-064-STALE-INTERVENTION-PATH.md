# WO-TIP-STAMP-P5-064-STALE-INTERVENTION-PATH

**Status:** DONE (pending merge)
**Priority:** LOW
**Gated:** no — tip-home retarget; product catalog already in `stopbanner.py` (`af62889`)

## Goal

Retarget canon cites of archive `twclient/intervention_labels.py` to tip
`tw2002_aiclient/cockpit/stopbanner.py`, and flip findings
`P5-064-STALE-INTERVENTION-PATH` to DONE.

## Scope

- `canon/architecture/control-and-escalation.md`
- `canon/surfaces/mode-line-and-teach-controls.md`
- `canon/surfaces/visual-language.md`
- `canon/findings.md`
- `tw2002_aiclient/cockpit/stopbanner.py` module docstring (catalog-home note)
- This WO file

## Out of scope

- Deleting BANKED `tests/test_intervention_labels.py` / catalog BANKED rows
- Spectate-layout port of the catalog

## Accept

1. Live architecture/surface canon no longer names tip-home as `intervention_labels.py`.
2. Findings row DONE; BANKED archive test called out as separate.
3. live-prove: `n/a` (docs + docstring).

## Proof

`rg intervention_labels.py canon/architecture canon/surfaces` → archive-only / none as tip-home;
STATUS SHA.
