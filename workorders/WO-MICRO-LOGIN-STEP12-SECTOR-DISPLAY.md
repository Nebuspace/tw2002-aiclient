# WO-MICRO-LOGIN-STEP12-SECTOR-DISPLAY — H1 vs H2 for microblaster step-12 stall

**Status:** BANKED · MED · login-flow coverage  
**Posted:** 2026-07-28T12:28Z · hub (from #156 live-prove SKIP + CC analysis 12:17Z)  
**Refs:** `login.py` `_POST_GAME_SELECT_PROGRESS` · `WO-MICRO-UNKNOWN-STEP6-CORPUS.md` precedent

## Goal

Resolve `login_failed:automaton_stuck:classification='sector_display':step=12` on `microblaster_network` with **evidence**, not a blind allow-list edit.

## Hypotheses

- **H1:** Genuine in-game `sector_display` after game select → allow-list may need `sector_display` in `_POST_GAME_SELECT_PROGRESS`.
- **H2:** Pre-game banner misclassified by loose `sector_display` matcher → tighten classifier; allow-list edit would worsen false latch.

## Scope

- Redaction-safe corpus capture at step-12 stall (matrix / isolated `TW_CONFIG_DIR` pattern; no secrets in-tree)
- Analysis note: H1 vs H2 with screen evidence
- **One** fix path in a follow-on EXEC WO (classify tighten **or** allow-list add) — not both guessed

## Out of scope

- Riding in coach-port or W5 PRs
- Inventing `screen_class` names without corpus

## Accept

- Corpus + analysis committed under `audit/` OR honest blocked note
- Hub-filed classify/login fix WO with explicit H1/H2 ruling

## Proof

STATUS with tip SHA; no live ensure without hub GO unless sacrificial profile already authorized.
