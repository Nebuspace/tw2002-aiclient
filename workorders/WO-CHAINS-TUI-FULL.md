# WO-CHAINS-TUI-FULL — Full Trade-Loop-Chains library modal (`L)chains`)

**Status:** OPEN · STAGED · **blocked on WO-CHAIN-DETECT-WIRE** (+ #116 taught path preferred)  
**Posted:** 2026-07-27T21:35:00Z · Max priority tranche ③  
**Seat:** open (CC+Fable for UI chrome if available)  
**Depends:** detection wire · canon modal prose  
**Refs:** `canon/surfaces/mode-line-and-teach-controls.md` · `visual-language.md` · `trainer-cockpit.md`

## Goal

Ship the **full** `L)chains` Trade-Loop-Chains library popup: discovered chains from detection **and** taught loops; select → confirm-gate → arm launch. Empty state `○ ○  no trade loop yet`.

## Accept

1. `L` opens modal; dismiss without arm.  
2. Discovered rows show sectors / cr/turn / hops from detection.  
3. Taught rows from loop store.  
4. Select + confirm arms launch (`autoloop_start` or equivalent); bare Enter never fires.  
5. Explore `E` path unchanged.  
6. PR + STATUS + suite; live optional.

## Constraints

- Money-path confirm-gate non-negotiable.  
- No EV finder inside the modal — display only what detection + store already know.  
- Serialize with #116 if still open on `app.py` / hint band.
