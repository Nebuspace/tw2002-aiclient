# WO-P6-080…088 — APP autopilot + rule engine · PREP

> Status: **PREP** 2026-07-25 · tip `5b848f0` docs / product `d4a8829` (+ CC HARDEN WIP unstaged) · seat `impl-aiclient-cursor`  
> Phase: 6 · Type: PREP (inventory + tightened Accept/Proof) · Execute: hub HANDOFF only  
> Canon: `canon/architecture/app-autopilot-model.md` · `canon/architecture/rule-macro-engine.md` · `canon/engine/screen-understanding.md` · `canon/engine/macros.md` · `canon/engine/priority-engine.md`  
> Refs: `ULTRACODE-WO-INVENTORY.md` Phase 6 · `WO-AUDIT-PHASE6-PREP.md` · scout tip-map (080 PARTIAL · 085/086 LIVE · rest MISSING)

**No product edited in this WO.** Live-state below is tip reality only.

---

## 0. Strategic framing

- **Phase 5 still open** — 062–072 MISSING; 061 Human→App **PARKED** (Max B′/C). Phase 6 must not invent teach/STOP/arm chrome.
- **AI never live-drives.** Autopilot = taught-screen App sender only; no `ai_pilot` mode; no live AI actor.
- **What already landed (tip):** `session/classify.py` (login/screen class) · `control_lock` `{app,human,spectate}` · `VALID_SENDERS={app,human}` · vocabulary gate (no AI-PILOT UI).
- **What Phase 6 still owes:** structured state parse · guarded rules · macro replay halt · stop-on-unknown loop · re-validate · MODE_AI_PILOT cleanup (daemon residual if any) · auto-haggle archetype · priority ranks taught-only.
- **HOLDs:** F2 · G2–G4 · north-star · Human→App · auth/secrets · HARDEN-ATTACH (CC product).

---

## 1. Tip inventory (vs canon target)

| Piece | Tip `d4a8829`+ | Notes |
|---|---|---|
| Screen class (`classify_screen`) | **LIVE** | `session/classify.py` → login/guardian/protocol |
| Structured state parse (`state_parser`) | **MISSING** | Cited deferred in `protocol.py` / `goals.py` |
| Guarded rule schema | **MISSING** | No load/store rule module |
| Macro capture + replay halt | **MISSING** | LoopPlayer / SkillRecorder cut (`daemon.py`) |
| Autopilot stop-on-unknown | **MISSING** | `autopilot.py` not ported |
| Re-validate every cycle | **MISSING** | Depends on 083 |
| MODE_AI_PILOT retired (product) | **LIVE** (gated) | Lock modes + UI vocabulary gate; archive tests may still expect AI-PILOT |
| Actor enum `{app,human}` | **LIVE** | `session.VALID_SENDERS` |
| Auto-haggle as guarded rule | **MISSING** | Protocol defers `haggle` |
| Priority engine ranks taught only | **MISSING** | FOCUS chrome kinds only; no engine |

---

## 2. Per-PWO Accept + Proof

### PWO-080 — Screen class + state parse (VERIFY/HARDEN) — **PARTIAL**
- **Live state:** classify LIVE; state_parser MISSING.
- **Accept:** Settled screen → `{class, state}` fixtures green; status/panel keys can be fed without inventing EV live-send.
- **Proof:** classify fixtures · state parse unit · protocol status keys non-empty under fixture.
- **Hazards:** Do not claim panel chrome DONE as data LIVE (status→panel wire gap).

### PWO-081 — Guarded rule schema (BUILD)
- **Depends-on:** 080
- **Accept:** when+guards→macro load/store; no live drive on load.
- **Proof:** unit schema round-trip.
- **Hazards:** Scaffold ≠ fire path.

### PWO-082 — Macro capture + replay halt (BUILD)
- **Depends-on:** 067 · 081
- **Accept:** Divergence halts; no guess-send.
- **Proof:** unit + FakeDaemon.
- **Hazards:** Secrets redaction on capture.

### PWO-083 — Autopilot loop stop-on-unknown (HARDEN)
- **Depends-on:** 081 · 064
- **Accept:** Unknown→STOP; App does not send.
- **Proof:** unit+live halt.
- **Hazards:** Needs STOP banner (064) for presentation.

### PWO-084 — Re-validate every cycle (HARDEN)
- **Depends-on:** 083
- **Accept:** Multi-cycle re-match; halt on drift.
- **Proof:** unit drift inject.

### PWO-085 — Remove/replace MODE_AI_PILOT (HARDEN) — **LIVE gated**
- **Live state:** Product lock has no `ai_pilot`; UI gate LIVE.
- **Accept residual:** Close findings / archive-test rehab if still expecting AI-PILOT; prove no live ai sender.
- **Proof:** `rg` + vocabulary tests · ledger actor∈{app,human}.

### PWO-086 — Actor enum {app,human} only (HARDEN) — **LIVE**
- **Live state:** `VALID_SENDERS` LIVE.
- **Accept residual:** Ledger rows when LedgerWriter lands (025/094).
- **Proof:** send reject on bad sender · ledger sample when available.

### PWO-087 — Auto-haggle as guarded rule (HARDEN)
- **Depends-on:** 081
- **Accept:** Built-in rule archetype; never silent money send without guards.
- **Proof:** pytest+fixture.

### PWO-088 — Priority engine ranks taught only (HARDEN)
- **Depends-on:** 081 · 034
- **Accept:** Never picks unknown screens; no EV-every-tick driver revival.
- **Proof:** unit ranking.

---

## 3. Depends-on graph

```
classify LIVE ──► 080 (state parse) ──► 081 (rules)
                                      ├─► 082 (w/ 067)
                                      ├─► 083 (w/ 064) ──► 084
                                      ├─► 087
                                      └─► 088
085/086 mostly LIVE — residual close with ledger/test rehab
```

**Suggested first execute after PREP Accept:** **080 state_parser / status wire** (unblocks panel honesty + rules).

---

## 4. Hazards

1. Do not invent Phase-5 product (062–072) under Phase-6 cover.
2. Do not invent Human→App keys.
3. Status→panel wire is honesty-critical — chrome LIVE ≠ data LIVE.
4. Tripwire / allowlist for any new App send sites.
5. Archive `twclient` tests expecting AI-PILOT are not product UI — rehab separately.

---

## 5. Execute readiness

PREP complete when Accept’d. Product seat stays idle on 080+ until hub HANDOFF. Cursor may tick inventory PREP→READY notes after Accept.
