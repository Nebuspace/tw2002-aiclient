# WO-INFRA-GENERALIZE-ADR-REVERIFY-CADENCE-LINT

**Priority:** MED  
**Gated:** no  
**Claimed-by:** impl-aiclient-h1

## Goal

Nebuspace `.samantha/scripts/adr-reverify-cadence-lint.py` hardcodes
`sw2102-docs/ADR` + `README.md`. tw2002-aiclient's `canon/ADR/index.md` flagged the
same gap ("port the convention before the set grows"). Ship a generalized lint in
**this** repo that defaults to `canon/ADR` + `index.md` and accepts `--dir` /
`--index` for other trees.

## Scope

- `scripts/adr-reverify-cadence-lint.py` (new)
- `tests/test_adr_reverify_cadence_lint.py` (new)
- `canon/ADR/index.md` (pointer to the script)
- This WO file

## Out of scope

- Editing the Nebuspace `.samantha` copy (hub-owned; may later call this script or
  gain matching args in a separate hub change)
- Mass re-stamping of ADRs

## Accept

1. `python3 scripts/adr-reverify-cadence-lint.py` exits 0 on tip `canon/ADR`
2. `--dir` / `--index` work on a fixture tree (missing/stale/mismatch covered)
3. Tests green

## Proof

```bash
python3 scripts/adr-reverify-cadence-lint.py --json
.venv/bin/python -m pytest tests/test_adr_reverify_cadence_lint.py -q -n0
```

live-prove: n/a (infra script; no session/login/play path)
