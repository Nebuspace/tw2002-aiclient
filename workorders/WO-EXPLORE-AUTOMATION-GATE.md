# WO-EXPLORE-AUTOMATION-GATE — Finish automated exploration (pre–trade-chain gate)

**Status:** OPEN · READY · **NEXT after #116**  
**Posted:** 2026-07-27T21:35:00Z · Max priority: trade-chain TUI+detect after explore done  
**Seat:** open (CC preferred if free; else Cursor)  
**Depends:** Play explore L1–L4 already on main; tip-check remaining gaps below  
**Refs:** `.samantha/plans/trade-loop-chains-after-explore-20260727.md` · `canon/strategy/exploration-policy.md`

## Goal

Close the **automated exploration gate** so world-model growth (warps + **ports**) is good enough to feed chain detection. This is the hard prerequisite Max set before full Trade Loop Chain work.

## Accept (E1–E4)

1. **E1** Map-fill / frontier: armed explore runs until turn budget **or** frontier exhausted; typed halt reason.  
2. **E2** Port persistence: visiting a port sector writes commodity buy/sell posture into world model (usable by future `trade_adapter`).  
3. **E3** At least **map-fill** and **find-StarDock** intents armable from Play (or documented honest subset with Max/hub ACK).  
4. **E4** Stop-on-unknown: unrecognized sector UI never silent-wanders.  
5. Live proof on sacrificial profile + suite + STATUS with SHA.

## Constraints

- No EV autopilot · no trade-chain finder in this WO · no `canon/` Accepted-number invent.  
- Confirm-gated arms only.

## Proof

Live explore session artifact (tmux/capture or audit md) showing map growth + ≥1 port record; unit pins for halt reasons.
