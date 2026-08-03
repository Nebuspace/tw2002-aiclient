# WO-P8-100…107 — Strategy as taught behaviors · PREP

> Status: **PREP** 2026-08-03 · tip honesty · seat `impl-aiclient-cursor`  
> Phase: 8 · Type: PREP (inventory + tightened Accept/Proof) · Execute: hub HANDOFF only  
> Canon: `canon/strategy/port-economics.md` · `trade-loops.md` · `exploration-policy.md` · `toll-and-defense.md` · `special-formations.md` · `planet-colonization.md` · `ship-progression.md`  
> Refs: `ULTRACODE-WO-INVENTORY.md` Phase 8 · parent `WO-AUDIT-PHASE789-PREP.md`

**No product edited in this WO.** Live-state below is tip reality only (`aad330c`).

---

## 0. Strategic framing

- **Phase 7 residuals** — 092 LIVE kernel (introspector deferred); 100 LIVE on tip. Do not invent introspector under 100 cover.
- **Human-approved only.** Strategy modules recommend / rank / STOP; purchases and Genesis remain human one-shots.
- **What already landed (tip):** chains/trade_adapter · trade_driver · explore BFS · fighter toll policy · formations catalog · coach cards for genesis/holds.
- **What Phase 8 still owes:** colonization confirm TTY · ship-upgrade decision engine (100+114 LIVE).
- **HOLDs:** money-path live arms without Max GO · inventing Human→App · AI live-drive.

---

## 1. Tip inventory (vs canon target)

| Piece | Tip `aad330c` | Notes |
|---|---|---|
| Port economics params | **LIVE** | `port_economics.py` HypothesisParam substrate · `trade_adapter` re-exports · coach port keys tagged; 114 CI LIVE |
| Trade loop define/rank | **LIVE** | `chains.py` · `trade_adapter.py` · `chain_search.py` · `chain_detect.py` + tests |
| Trade loop run + depletion STOP | **LIVE** | `trade_driver.py` + suite collects `test_trade_driver.py` (26; depleted STOP proven) |
| Exploration frontier BFS | **LIVE** | `explore.py` · `session/sector_explore.py` + tests |
| Toll fight/pay/reroute | **LIVE** | `session/fighter_toll_policy.py` + tests |
| Formations locate/catalog | **LIVE** | `formations.py` · `world_stats.py` · `tests/test_formations_catalog.py` (WO-FORMATIONS-CATALOG-PORT) |
| Colonization + Genesis confirm | **DONE/PARTIAL** | Option A `genesis_confirm` seam LIVE (#368); Genesis adapter/send Option B HELD |
| Ship/holds upgrade recommend | **DONE/PARTIAL** | Option A `ship_upgrade_decision` + DECISIONS wire LIVE (#368); purchase adapter Option B HELD |

---

## 2. Per-PWO Accept + Proof

### PWO-100 — Port economics params (BUILD) — **LIVE**
- **Depends-on:** 092 (satisfied · tip `73e7428`)
- **Live state:** `port_economics.py` HypothesisParam substrate; `trade_adapter` re-exports floors/ceiling/spread; coach port keys load via tagged `params.json`.
- **Accept residual:** none (PWO-114 CI enforcement LIVE).
- **Proof:** `tests/test_port_economics.py`.
- **Hazards:** Do not invent 092 under 100 cover — held.

### PWO-101 — Trade loop define/rank (BUILD) — **LIVE**
- **Depends-on:** 100 · 081
- **Accept residual:** harden only if Execute finds ranking drift vs canon.
- **Proof:** `tests/test_chains.py` · `tests/test_trade_adapter.py`.
- **Hazards:** Ranking ≠ live send.

### PWO-102 — Trade loop run + depletion STOP (BUILD) — **LIVE**
- **Depends-on:** 101 · 083
- **Live state:** `trade_driver.py` + `tests/test_trade_driver.py` in default suite (26 FakeChainSession tests; `test_depleted_stock_stops_the_chain_cleanly`).
- **Accept residual:** live TWGS arm remains Max-gated / separate prove — offline suite gate met.
- **Proof:** default `pytest` collects + green on `test_trade_driver.py`.
- **Hazards:** Money-path live arm still Max GO; Auto-haggle still OFF (#337 residual).

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

### PWO-106 — Colonization recommend + Genesis confirm (BUILD) — **DONE/PARTIAL** (Option A seam LIVE)
- **Depends-on:** 096
- **Live state:** `genesis_confirm.py` — armconfirm-reuse default-deny; `genesis_send_if_confirmed` refuse-without-CONFIRM; no production caller yet.
- **Accept residual:** Option B Genesis adapter + TTY fire path (fresh GO).
- **Proof:** `tests/test_genesis_confirm.py`.
- **Hazards:** Never auto-Genesis; never bypass the seam.

### PWO-107 — Ship/holds upgrade recommend (BUILD) — **DONE/PARTIAL** (Option A engine LIVE)
- **Depends-on:** 096
- **Live state:** `ship_upgrade_decision.py` ported; DECISIONS surfaces `UpgradeDecision` when status carries inputs.
- **Accept residual:** Option B purchase adapter behind armconfirm (fresh GO).
- **Proof:** `tests/test_ship_upgrade_decision.py`.
- **Hazards:** Money-path purchase stays HELD; recommend ≠ buy.

---

## 3. Depends-on graph

```
092 LIVE kernel ──► 100 LIVE ──► 101 LIVE ──► 102 LIVE
091·083 ──► 103 LIVE
081 ──► 104 LIVE
091 ──► 105 LIVE
096 ──► 106 DONE/PARTIAL (Option A)
096 ──► 107 DONE/PARTIAL (Option A)
```

**Suggested first execute after PREP Accept:** Option B halves for 106/107 (propose-first) *or* ungated Phase-8 residual. 102 suite-gate CLOSED. Full 100 waits on 092.

---

## 4. Hazards

1. Do not claim Phase-8 COMPLETE because several modules are LIVE — PARTIAL residuals are load-bearing.
2. Money-path live arms need Max sacrificial GO.
3. Coach cards ≠ decision engines.
4. Auto-haggle trade-arm is a separate WO (`WO-AUTOHAGGLE-TRADE-ARM` candidate), not 102 cover.

---

## 5. Execute readiness

PREP ready for hub Accept of this docs WO. Product Execute = separate HANDOFF.
