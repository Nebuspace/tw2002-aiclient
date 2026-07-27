# WO-CHAIN-DETECT-WIRE — World model → hops → recompute chains

**Status:** OPEN · STAGED · blocked on WO-CHAIN-DETECT-PORT · class-posture in Accept  
**Posted:** 2026-07-27T21:35:00Z · Max priority tranche ②  
**Seat:** open  
**Depends:** `WO-CHAIN-DETECT-PORT` · explore gate port persistence (E2)  
**Refs:** `canon/engine/world-model.md` · `canon/strategy/trade-loops.md`

## Goal

Wire detection to live world-model port records: after explore (or on demand), recompute known TradeHops and best ProfitChain(s) for the active `world_id`.

## Accept

0. **Class-derived posture path** (hub GO 2026-07-27): hops from letter triples with margin unknown — not empty forever waiting on docked commodities.
1. Given a world model with ≥2 complementary ports (class and/or commodities), detection yields a chain (or honest empty).  
2. Recompute is idempotent; no sends.  
3. Surface a typed API/adapters call the TUI can read (no curses in this WO).  
4. PR + STATUS + suite (+ optional live after explore on sacrificial world).

## Constraints

- Finder only — operator arms later via TUI / #116 path.  
- Do not invent autonomous rotation on depletion.
