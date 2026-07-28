# WO-COACH-CHAIN-TRIGGER — Discovered-chain coach callout via coaching-engine

**Status:** OPEN EXECUTE · MED · Claude Code preferred  
**Posted:** 2026-07-28T01:25Z · hub (split from #128 Accept 5)  
**Unbanked:** 2026-07-28T12:15Z · hub under Max carte blanche (W4/#147 landed; `infer_coach_triggers` + strategy cards already in tree)  
**Seat:** impl-claudecode-aiclient  
**Depends:** `WO-CHAIN-DETECT-WIRE` / #128 · #147 CHAINS-TUI · `canon/engine/coaching-engine.md` (substrate present — not blocked)

## Goal

Surface discovered pair / profit-chain opportunities as **authored coach cards** via
`infer_coach_triggers` + `compose_decisions_coach` + `coach_kb` — never a bespoke
`format_coach_callout` that invents card text (canon forbids competing sources).

Cards already ship in `data/coach/strategies.json` (`pair_trade_loop`, `longest_profit_chain`).
`cockpit/decisions.py` deferred this wiring deliberately; this WO is that follow-on.

## Scope

- Wire a discovered-chain trigger into the existing coaching-engine path
- Thin product consumer on DECISIONS (or documented sibling) when wire result present
- Do **not** invent card prose; do not add a second formatter

## Constraints

- Taught `L)chains` arm list stays taught-only (money path)
- No new competing coach text source
- No autonomous arm

## Accept

1. Trigger fires authored card(s) for discovered pair / chain opportunity shapes.
2. No bespoke invented callout formatter.
3. Suite + STATUS; live prove if DECISIONS paint path is live-touching.

## Refs

- Hub #128 design ACK 2026-07-28 (Accept 5 SPLIT)
- CC DECISION-NEEDED 2026-07-28T01:26:40Z §3
- `canon/engine/coaching-engine.md`
