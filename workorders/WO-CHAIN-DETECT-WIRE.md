# WO-CHAIN-DETECT-WIRE — World model → hops → recompute chains

**Status:** OPEN · Accept 0–4 DONE origin `c56f852` (#128) · **residual:** Accept 5's `chain_as_library_row` resolves to no product definition (canon + one test cite it only) — rendering shipped via #147; the named bridge shape never existed · reviewed 2026-07-28
**Posted:** 2026-07-27T21:35:00Z · Max priority tranche ②  
**Seeded for execute:** 2026-07-28T00:51Z · hub  
**Seat:** impl-claudecode-aiclient  
**Depends:** `WO-CHAIN-DETECT-PORT` ✅ · `WO-CHAIN-SEARCH-BUDGET` ✅ · explore gate port persistence (E2) ✅  
**Refs:** `canon/engine/world-model.md` · `canon/strategy/trade-loops.md` · `workorders/WO-CHAIN-SEARCH-BUDGET.md`

## Goal

Wire detection to live world-model port records: after explore (or on demand), recompute known TradeHops and best ProfitChain(s) for the active `world_id`.

## Accept

0. **Class-derived posture path** (hub GO 2026-07-27): hops from letter triples with margin unknown — not empty forever waiting on docked commodities.
1. Given a world model with ≥2 complementary ports (class and/or commodities), detection yields a chain (or honest empty).  
2. Recompute is idempotent; no sends.  
3. Surface a typed API/adapters call the TUI can read (no curses in this WO).  
4. PR + STATUS + suite.  
5. **Canon renderings (hub GO 2026-07-27 · Scope-1 correction):** inject discovered chains via a `chain_as_library_row`-shaped bridge into the loops/composer consumer; land `format_coach_callout` (or equivalent) on the coach surface. Pure bridge helpers may live beside detect; callout formatter in cockpit/coach — do not drop these as "parked archive."

## Proof

- Offline: suite green + junitxml counts; mutation or differential pins for posture path + bridge/callout where feasible.
- **Live prove — REQUIRED (not optional):** this WO flips #127's structural `n/a`. Composition of adapter + finder onto a **real world model** is the first product path where truncation behaviour, class-derived posture, and coach-callout rendering meet live bytes. Hub diversity bar applies (≥3 catalog hosts with ≥1 NEW and ≥1 RETURNING across the run, or honest SKIP cells with reason). Safe halves (read-only world load / recompute without arm) = hub GO; turn-spending arm remains Max sacrificial GO only.
- Vocabulary: do **not** post `n/a` here unless a Max-gated block is explicit; `NOT-ATTEMPTED` is never Acceptable as `n/a`.

## Constraints

- Finder / wire only — operator arms later via TUI / #116 path.  
- Do not invent autonomous rotation on depletion.
- Use `find_profit_chains_with_note` (or equivalent) so truncation is never silent.
- No new external dependencies.
