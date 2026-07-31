# WO-CLASSIFY-MAIN-COMMAND-SECTOR-POSITIVE (optional LOW follow-on)

**Status:** READY · EXECUTE · LOW · Cursor (`impl-aiclient-cursor`)
**Seat:** `impl-aiclient-cursor`  
**Posted:** 2026-07-27T06:03:26Z  
**Seat:** Cursor volume after teach wave or anytime  
**Depends:** `de6ca30` Main Menu refuse already on main  

## Goal

Strengthen `main_command` with a **positive** in-game sector require (`:[\\d+]` + Help cue) so Unicode-confusable / odd door chrome cannot land on `main_command` via refuse-list gaps alone.

## Scope

- `classify.py` `_is_main_command` — require integer sector slot (not only refuse `[Main Menu]`)
- Pins + mutation; keep existing main_command fixtures green

## Accept

Menu/door forms → not `main_command`; sector `[N] (?=Help)?` → `main_command`; mutation pin.

## Proof

`pytest tests/test_classify.py -k main_command`
