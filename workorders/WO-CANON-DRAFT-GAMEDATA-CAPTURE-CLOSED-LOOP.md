# WO-CANON-DRAFT-GAMEDATA-CAPTURE-CLOSED-LOOP

**Status:** OPEN (in PR) — tip-close / verify-only  
**Priority:** HIGH (queue) · **Outcome:** no doc edit needed  
**Claimed-by:** impl-aiclient-cursor  
**Source:** Cycle-36 / queue-aiclient.md (third re-flag of same doc-rot)

## Goal

Update canon if it still claimed StarDock capture→persist "wiring not yet built."

## Tip-verify (2026-08-06 @ main `7c0cbc5`)

| Check | Result |
|---|---|
| `canon/engine/game-data-store.md:217` | **Already LIVE:** "Opportunistic StarDock capture→persist is LIVE on tip." names `game_data_capture.py`, settle-edge, never-send |
| `canon/engine/game-data-store.md:210-216` | Distinguishes `tw probe` L0 (banner classify only — still not a row filler) from capture path — matches WO's "narrower gap distinct" note |
| Product wire | `app.py` constructs `GameDataCapture()` and calls `gamedata_capture.tick(play, profile)` on idle tick |
| Stale string | Repo grep for "wiring not yet" / "missing link" as open claim: only historical "was the missing link" past-tense in the LIVE bullet |

## Decision

**Tip-close — no canon edit.** Sibling row `WO-CANON-DRAFT-GAMEDATA-CAPTURE-LOOP-WIRED` already marked DONE/subsumed for the same evidence. This Cycle-36 HIGH row is the same false-premise re-flag; closing with evidence so the next Half-2 does not stage it a fourth time.

## Accept

- [ ] Tip-verify table stands
- [ ] WO evidence file only (this file)
- [ ] No product / no doc body change beyond this WO

## live-prove

`n/a` — verify-only / docs-rot false premise.
