# WO-P7-090…096 — World stores & learning substrate · PREP

> Status: **PREP** 2026-08-03 · tip honesty · seat `impl-aiclient-cursor`  
> Phase: 7 · Type: PREP (inventory + tightened Accept/Proof) · Execute: hub HANDOFF only  
> Canon: `canon/engine/world-identity.md` · `world-model.md` · `game-data-store.md` · `menu-map-and-introspection.md` · `trace-ledger.md` · `candidate-mining.md` · `coaching-engine.md`  
> Refs: `ULTRACODE-WO-INVENTORY.md` Phase 7 · parent `WO-AUDIT-PHASE789-PREP.md`

**No product edited in this WO.** Live-state below is tip reality only (`aad330c`).

---

## 0. Strategic framing

- **Phase 6 residuals still open** — 087 PARTIAL (trade_driver Auto-haggle OFF); 088 DONE/PARTIAL (FOCUS Layer-2; full priority kernel parked). Phase 7 must not invent Phase-6 execute under PREP cover.
- **AI never live-drives.** World/crawl/coach surfaces are substrate + recommend-only; no live AI sender.
- **What already landed (tip):** world-id helpers · world-model persist · menu crawler · coach engine · partial ledger/transcript paths.
- **What Phase 7 still owes:** colocated world-id across *all* stores · two-layer game-data store · per-dispatch trace ledger · candidate mining (no LLM) · coach TTY polish residuals as Execute scopes them.
- **HOLDs:** F2 · G2–G4 · north-star · Human→App · auth/secrets money-path · sacrificial live crawl without Max GO.

---

## 1. Tip inventory (vs canon target)

| Piece | Tip `aad330c` | Notes |
|---|---|---|
| World-id keying | **PARTIAL** | `world_identity.py` · `world_model.py` · `world_stats.py` · `session/sector_explore.py` — not every store imports the scheme (`loops/store.py` still flat) |
| World-model persist/read | **LIVE** | `world_model.py` + `tests/test_world_model.py`; state_parser can feed writes |
| Game-data two-layer store | **MISSING** | Canon only; banked `test_game_data*` / `test_game_knowledge*` deleted per `pytest.ini` |
| Menu-map read-only crawl | **LIVE** | `menu/crawler.py` · `crawl_driver.py` · `knowledge.py` + crawler tests; live protocol verb still deferred |
| Trace ledger append | **PARTIAL** | transcript/logging + actor attribution; no per-dispatch LedgerWriter semantic schema on tip |
| Candidate mining (no LLM) | **MISSING** | `tw mine` / miner tests banked or archive `twclient.analyze` only |
| Coaching tips read-only | **LIVE** | `coach_engine.py` · `coach_kb.py` · `data/coach/*` · cockpit decisions + tests |

---

## 2. Per-PWO Accept + Proof

### PWO-090 — World-id keying everywhere (HARDEN) — **PARTIAL**
- **Depends-on:** 014
- **Live state:** helpers + world_model/stats/explore use a scheme; colocated-everywhere not proven.
- **Accept residual:** every durable store keys by the same world-id scheme; loops/macros colocated or explicitly exempted with DECISION.
- **Proof:** unit + `rg` audit of store roots.
- **Hazards:** Do not silently migrate operator data without a migrate WO.

### PWO-091 — World-model persist/read (BUILD) — **LIVE**
- **Depends-on:** 090 · 080
- **Live state:** sector DB grows via `world_model.py`.
- **Accept residual:** harden only if Execute finds schema drift vs canon.
- **Proof:** `tests/test_world_model.py` · explore tick write path.
- **Hazards:** Claiming LIVE ≠ claiming every panel consumes it.

### PWO-092 — Game-data two-layer store (BUILD) — **MISSING**
- **Depends-on:** 090
- **Accept:** Semantics≠DATA layers; no hardcoded ship/port stats in product modules.
- **Proof:** audit + unit round-trip when module lands.
- **Hazards:** Do not revive archive BANK tests as product without a port WO.

### PWO-093 — Menu-map read-only crawl (BUILD) — **LIVE**
- **Depends-on:** 090
- **Live state:** crawler + knowledge present; never-commit crawl artifact discipline in place for offline tests.
- **Accept residual:** live sacrificial crawl protocol verb if still deferred — own Execute + Max GO.
- **Proof:** crawler unit/chokepoint tests.
- **Hazards:** Live crawl is sacrificial; never commit crawl dumps.

### PWO-094 — Trace ledger append semantics (HARDEN) — **PARTIAL**
- **Depends-on:** 025 · 041
- **Live state:** transcript_tail / logging_util / actor attribution; LedgerWriter cut noted in attach suite.
- **Accept residual:** per-dispatch semantic rows matching `trace-ledger` canon.
- **Proof:** unit schema + sample append.
- **Hazards:** Secrets must never appear in ledger rows (pairs with 111).

### PWO-095 — Candidate mining no LLM (BUILD) — **MISSING**
- **Depends-on:** 094
- **Accept:** recurring patterns → candidates dry-run; no LLM required.
- **Proof:** unit dry-run.
- **Hazards:** Archive `twclient.analyze` is not the reborn miner.

### PWO-096 — Coaching tips read-only (BUILD) — **LIVE**
- **Depends-on:** 036 · 091
- **Live state:** coach engine + KB + cockpit decisions; options never act.
- **Accept residual:** surface polish / new cards are Execute WOs, not PREP gaps.
- **Proof:** `tests/test_coach_engine.py` · decisions tests.
- **Hazards:** Coach must remain recommend-only (pairs with 113).

---

## 3. Depends-on graph

```
090 PARTIAL ──► 091 LIVE
            ├─► 092 MISSING
            └─► 093 LIVE
025/041 ──► 094 PARTIAL ──► 095 MISSING
036·091 ──► 096 LIVE
```

**Suggested first execute after PREP Accept:** **PWO-092 game-data store** (unblocks honest 100 economics) *or* **PWO-094 ledger semantics** (unblocks 095) — hub picks; both are real MISSING/PARTIAL kernels.

---

## 4. Hazards

1. Do not invent Phase-8 strategy under Phase-7 PREP cover.
2. Do not treat canon-only as LIVE.
3. Sacrificial menu crawl needs Max GO for live arm.
4. Banked archive tests are not product evidence.

---

## 5. Execute readiness

PREP ready for hub Accept of this docs WO. Product Execute requires separate HANDOFF per PWO (or small batch with explicit not-in-batch list).
