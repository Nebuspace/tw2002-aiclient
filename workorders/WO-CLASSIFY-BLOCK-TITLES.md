# WO-CLASSIFY-BLOCK-TITLES

**Status:** OPEN · PARKED · Max (vocab + money-screen)  
**Posted:** ~2026-07-25 (CC tip built; push parked 18:37:06Z)

## Goal

Generalize block-title classification (StarDock folds into block-title generalisation). Tip introduces labels `stardock_cargo_hold_quote` + `stardock_shipyard_listing` with exclusivity-first / asymmetry-trap awareness; prefer fewer confident classes over shaky coverage.

## Scope

- `tw2002_aiclient/` classify path + tests (when unparked)
- Local tip held (historically `628077a` / `bd883fa` / `ae1618b` — do not land without Max GO)

## Constraints

- `screen_class` is a **closed fixed vocabulary** in `canon/engine/screen-understanding.md` — new labels are a canon amendment → **human-gated**.
- Money-screen naming + never-auto-action pin also Max-gated.
- Do not push; do not rebase-away the tip until Max rules.

## Accept (after Max GO)

Tip lands with hub Accept; vocab / money-screen rulings reflected in canon + code; independent `_UNSAFE_SCREEN_PATTERNS` / compensating controls preserved.

## Proof

STATUS + SHA after unpark; hub Accept.

## Refs

- Hub ACK classify merge @ 18:12:06Z · park @ 18:37:06Z
- `canon/engine/screen-understanding.md` closed vocab
- Max pending: add `stardock_*` labels vs rename; money-screen name ok with never-auto-action?
