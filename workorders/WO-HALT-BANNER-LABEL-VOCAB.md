# WO-HALT-BANNER-LABEL-VOCAB

**Status:** **DONE** · origin `f3b2067` (`f3b2067c2b5df5b920efeb6a3d3be646847c5b71`) · product (`cockpit/stopbanner.py` + pins + escalation catalog) · Cursor seat 2026-07-26
**Posted:** 2026-07-26 · hub batch: 13 of 16 halt reason codes render RAW
**Max ruling (1A):** expand human vocab for the 13 · **unmapped stay RAW** (not loud)

## Goal

Land human labels for the 13 halt-banner reason codes that currently render RAW.
Unmapped codes remain RAW (do not invent loud wrappers).

## Scope

- Label map / intervention labels surface (exact paths per tip)
- **Out:** money/auth-implying label invent beyond the 13 measured codes

## Accept

- 13 codes have human labels; unmapped still RAW; pin covers mapped vs unmapped

## Proof

Max ruling 1A. Tip `f3b2067`. All 16 `HALT_REASONS` labelled; unmapped still RAW.
`pytest tests/test_cockpit_stopbanner.py tests/test_credits_floor.py::test_which_of_the_new_codes_canon_already_has_a_label_for -n0`.
