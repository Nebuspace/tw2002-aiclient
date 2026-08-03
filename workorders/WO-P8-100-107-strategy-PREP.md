# WO-P8-100…107 — Strategy as taught behaviors · PREP

> Status: **PREP** 2026-08-03 · tip honesty · seat `impl-aiclient-cursor`  
> Phase: 8 · Type: PREP (inventory + tightened Accept/Proof) · Execute: hub HANDOFF only  
> Canon: `canon/strategy/port-economics.md` · `trade-loops.md` · `exploration-policy.md` · `toll-and-defense.md` · `special-formations.md` · `planet-colonization.md` · `ship-progression.md`  
> Refs: `ULTRACODE-WO-INVENTORY.md` Phase 8 · parent `WO-AUDIT-PHASE789-PREP.md`

**No product edited in this WO.** Live-state below is tip reality only (`aad330c`).

---

## 0. Strategic framing

- **Phase 7 gaps block some Phase-8 Accepts** — notably 100 depends on 092 (game-data) which is MISSING; economics numbers today live in adapter/coach data.
- **Human-approved only.** Strategy modules recommend / rank / STOP; purchases and Genesis remain human one-shots.
- **What already landed (tip):** chains/trade_adapter · trade_driver · explore BFS · fighter toll policy · formations catalog · coach cards for genesis/holds.
- **What Phase 8 still owes:** port-economics module + hypothesis tags · trade_driver suite gate · colonization confirm TTY · ship-upgrade decision engine.
- **HOLDs:** money-path live arms without Max GO · inventing Human→App · AI live-drive.

---

## 1. Tip inventory (vs canon target)

| Piece | Tip `aad330c` | Notes |
|---|---|---|
| Port economics params | **PARTIAL** | `trade_adapter.py` floors/spreads · `data/coach/params.json` — no standalone port-economics store; depends on 092 |
| Trade loop define/rank | **LIVE** | `chains.py` · `trade_adapter.py` · `chain_search.py` · `chain_detect.py` + tests |
| Trade loop run + depletion STOP | **PARTIAL** | `trade_driver.py` present; default suite **ignores** driver tests |
| Exploration frontier BFS | **LIVE** | `explore.py` · `session/sector_explore.py` + tests |
| Toll fight/pay/reroute | **LIVE** | `session/fighter_toll_policy.py` + tests |
| Formations locate/catalog | **LIVE** | `formations.py` · `world_stats.py` · `tests/test_formations_catalog.py` (WO-FORMATIONS-CATALOG-PORT) |
| Colonization + Genesis confirm | **PARTIAL** | `formations.recommend_genesis` · coach `dead_end_planet` — no TTY Genesis one-shot gate |
| Ship/holds upgrade recommend | **PARTIAL** | coach `holds_first` + shipyard trigger tests; no TW-30 upgrade engine (`test_ship_upgrade_decision` banked) |

---

## 2. Per-PWO Accept + Proof

### PWO-100 — Port economics params (BUILD) — **PARTIAL**
- **Depends-on:** 092
- **Live state:** adapter/coach numbers exist; not full canon schema / hypothesis discipline.
- **Accept residual:** hypothesis-tagged params module; no silent hardcoded product stats.
- **Proof:** unit + tag presence (pairs with 114).
- **Hazards:** Do not invent 092 under 100 cover.

### PWO-101 — Trade loop define/rank (BUILD) — **LIVE**
- **Depends-on:** 100 · 081
- **Accept residual:** harden only if Execute finds ranking drift vs canon.
- **Proof:** `tests/test_chains.py` · `tests/test_trade_adapter.py`.
- **Hazards:** Ranking ≠ live send.

### PWO-102 — Trade loop run + depletion STOP (BUILD) — **PARTIAL**
- **Depends-on:** 101 · 083
- **Live state:** driver module exists; suite exclusion means gate does not prove it.
- **Accept residual:** STOP on depletion proven in default suite (or documented carve-out + live prove).
- **Proof:** un-ignore or dedicated job + fixture/live.
- **Hazards:** Money-path — Max GO for live arm; Auto-haggle still OFF (#337 residual).

### PWO-103 — Exploration frontier BFS (BUILD) — **LIVE**
- **Depends-on:** 091 · 083
- **Accept residual:** unknown-sector UI STOP already tied to explore/autoloop — Execute only if gaps found.
- **Proof:** `tests/test_explore.py`.
- **Hazards:** Live explore arm is separate from offline LIVE.

### PWO-104 — Toll fight/pay/reroute guards (BUILD) — **LIVE**
- **Depends-on:** 081
- **Live state:** NPC toll policy; combat escalates per module.
- **Proof:** `tests/test_fighter_toll_policy.py` (confirm collect not banked).
- **Hazards:** PvP aggression is 113 — do not conflate NPC toll with player-kill rules.

### PWO-105 — Formations locate/catalog (BUILD) — **LIVE**
- **Depends-on:** 091
- **Live state:** catalog + recommend-only.
- **Proof:** formations catalog tests.
- **Hazards:** Recommend ≠ auto-warp.

### PWO-106 — Colonization recommend + Genesis confirm (BUILD) — **PARTIAL**
- **Depends-on:** 096
- **Accept residual:** TTY Genesis human one-shot confirm before any App send.
- **Proof:** TTY/fixture confirm gate.
- **Hazards:** Never auto-Genesis.

### PWO-107 — Ship/holds upgrade recommend (BUILD) — **PARTIAL**
- **Depends-on:** 096
- **Accept residual:** purchase human-approved decision path (not coach card alone).
- **Proof:** unit + TTY confirm.
- **Hazards:** Money-path; do not revive banked tests as proof without port.

---

## 3. Depends-on graph

```
092 MISSING ──► 100 PARTIAL ──► 101 LIVE ──► 102 PARTIAL
091·083 ──► 103 LIVE
081 ──► 104 LIVE
091 ──► 105 LIVE
096 ──► 106 PARTIAL
096 ──► 107 PARTIAL
```

**Suggested first execute after PREP Accept:** **PWO-102 suite-gate honesty** (un-ignore/prove depletion STOP) *or* **PWO-106 Genesis confirm** — both close real PARTIAL without inventing 092. Full 100 waits on 092.

---

## 4. Hazards

1. Do not claim Phase-8 COMPLETE because several modules are LIVE — PARTIAL residuals are load-bearing.
2. Money-path live arms need Max sacrificial GO.
3. Coach cards ≠ decision engines.
4. Auto-haggle trade-arm is a separate WO (`WO-AUTOHAGGLE-TRADE-ARM` candidate), not 102 cover.

---

## 5. Execute readiness

PREP ready for hub Accept of this docs WO. Product Execute = separate HANDOFF.
