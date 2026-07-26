# WO-BLESSED-MACRO-DEFAULT

**Status:** **DONE** · origin `07225ea` (`07225ea2f43d38e431d0a376666f6e643be9f9c3`) · docs (`canon/engine/macros.md` + `loops/recorder.py` docstring) · Cursor seat 2026-07-26
**Posted:** 2026-07-26 · conflict: recorder/`blessed=True` default vs `macros.md` "inert until approved"
**Max ruling:** **blessed-by-default is OK** — align `macros.md` (and any stale "inert until approved" prose) to code; do **not** flip recorder default to inert.

## Goal

Canon matches shipped `blessed=True` default. Docs-only unless a second surface still claims inert-until-approved in product strings.

## Scope

- `macros.md` / related canon — exact files at tip
- **Out:** changing recorder default to require approval

## Accept

- Canon no longer says inert-until-approved as the product rule; blessed-by-default documented honestly

## Proof

Tip `07225ea`. Grep: no "every macro is inert until approved" / "Both are inert" product rule in `macros.md`; mined drafts still correctly "inert until a human promotes". Recorder docstring cites Max ruling — do not flip `blessed=True` default.
