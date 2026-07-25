# WO-P5-060…072 — Mode line, escalation & teach · PREP

> Status: **PREP + PWO-060 DONE + PWO-061 KERNEL DONE** 2026-07-25 · product tip `d4a8829` · seat `impl-aiclient-cursor` (OKF-STATUS-TRUTH-061-KERNEL)  
> Phase: 5 · Type: PREP (inventory + tightened Accept/Proof) · Execute: hub HANDOFF to product seat after Accept  
> Canon: `canon/surfaces/mode-line-and-teach-controls.md` · `canon/architecture/control-and-escalation.md` · `canon/engine/ai-teacher.md` · `canon/architecture/app-autopilot-model.md` · `canon/engine/coverage-metrics.md` · `canon/engine/macros.md` · `canon/architecture/rule-macro-engine.md`  
> Refs: `ULTRACODE-WO-INVENTORY.md` Phase-5 rows · Phase 4 CLOSED (`bba53d4`) · PWO-060 (`2ca3154`) · PWO-061 kernel (`d4a8829`) · Pending DOC-GAP-M-FROM-SPECTATE · DOC-GAP-POST-DETACH-COPY · DOC-GAP-SPECTATE-REVERSE-VS-PLAIN · **Max Ruled:** Mode=Ctrl-A · attached `M`=Move · no printable Mode · **Batch 1b CLOSED**

**No product edited in this OKF tick.** Live-state below is tip **`d4a8829`** unless a row still says MISSING/PARKED. **Do not read 061 as CLOSED** — kernel only.

---

## 0. Strategic framing

- **Phase 4 CLOSED** — human play loop LIVE: spectate → `M` attach → play → Ctrl-] detach → spectate (`bba53d4`).
- **Phase 5 owns presentation of the App/Human dual + teach/escalation**, not a second cockpit. One play shell; in-surface chrome.
- **Spectate is not a dual member** (canon) — muted `SPECTATE` is observation, not an App/Human toggle position. DOC-GAP-M-FROM-SPECTATE remains **Pending** (unsigned): shipped `M` is Spectate→Human; App↔Human return still owed here (061).
- **AI never live-drives.** Retire any `AI-PILOT` / `ai_pilot` UI string. Teach overlay is cyan/info, transient, never a mode-line dual seat. App chip = **green (`ok`)** deterministic autopilot (aspirational→buildable Accept on 060).
- **What 056/057 already satisfied:** Human/`MANUAL — YOU HAVE CONTROL` chip LIVE · `M` attach LIVE · Ctrl-] detach LIVE · no-send tripwire + attach allowlist LIVE · redaction on attach channel LIVE.
- **What Phase 5 still owes:** Human→App entry (061 Accept #2 — **Ruled:** Ctrl-A Mode; CC product HANDOFF live) · migrate Spectate→Human bare `M`→Ctrl-A · A/R/T teach strip · STOP banner + reason codes · arm/confirm · N5 operate cluster · coverage meter (App-vs-Human, AI≠live slice).
- **F2 HOLD** — ops `tw spectate` CLI still Max-gated. **G2–G4 HOLD** unchanged.
- **North-star** parked pending Max (1)(2) — this PREP does not unpark or invent one-cockpit prose beyond existing Phase-4 alignment.
- **Archive** = port-source only (`spectate_app` / `spectate_layout` badges) — never `import twclient`.
- **D1 harness:** Layer-A pure compose + FakeClient; Layer-B pty when chip/tone geometry matters; never `run/twd.sock` in Accept.

---

## 1. Tip inventory (vs canon target)

| Piece | Tip `d4a8829` | Notes |
|---|---|---|
| Control-strip seat label SPECTATE | **LIVE** (PWO-055 · `cockpit/control_seat.py`) | Muted/plain; not a dual member |
| Control-strip seat label MANUAL (Human) | **LIVE** (PWO-056 · reverse+warn lift in 060) | `MANUAL — YOU HAVE CONTROL`; `_safe_attached` defaults False |
| Unified **App** chip (green / no AI-PILOT) | **LIVE** (PWO-060 · `APP` / `ok`+bold+reverse) | Strict gate LIVE; App→Human path proven (061 kernel); **Human→App wire via Ctrl-A** — product HANDOFF `WO-P5-061-ENTRY` (CC) |
| `M` Spectate→Human attach | **LIVE** (PWO-056) · **migrate** | Hub 056 bare `M` today; Max 1b: migrate attach Mode to Ctrl-A (same WO or follow-on) |
| `M` App-hold→Human | **LIVE** (PWO-061 KERNEL · `d4a8829`) | Existing 056 attach wiring; test-only pins; zero product delta — retarget to Ctrl-A under 061-entry |
| Human→App entry trigger | **GO** (Batch 1b CLOSED) | **Ruled:** Ctrl-A = Mode; attached bare `M` = TW Move passthrough; no printable Mode |
| Ctrl-] detach → SPECTATE | **LIVE** (PWO-057) | Esc≠detach; post-detach copy DOC-GAP Pending; Ctrl-] from App-hold = unruled no-op (pinned) |
| Teach strip A / R / T affordances | **MISSING** | 066; keys unbound as teach moves |
| Analyze (`A`) on-demand | **MISSING** | 069 · `ai-teacher.md` |
| Record (`R`) macro wire | **MISSING** | 067 · `macros.md` |
| Assign-trigger (`T`) scaffold | **MISSING** | 068 · `rule-macro-engine.md` |
| Analyze draft → human approve | **MISSING** | 070 |
| STOP banner + typed reason codes | **MISSING** | 064 · `control-and-escalation.md` catalog |
| Intervention → Human keyboard | **PARTIAL** | Attach path LIVE; STOP-driven handoff **MISSING** (065) |
| Autopilot/Trainer arm UI | **MISSING** | 062 · `app-autopilot-model.md` |
| Confirm-to-arm dialog | **MISSING** | 063 · mode-line confirm-gate |
| N5 operate-the-app cluster | **MISSING** | 071; layout reserved control-strip left for N5 |
| Coverage / auto meter (App-vs-Human) | **MISSING** | 072 · `coverage-metrics.md`; no live AI slice |
| Daemon control_lock modes | **LIVE** ops | Product must not surface `ai_pilot` as a chip |

---

## 2. Per-PWO Accept + Proof

### PWO-060 — App/Human badge (no AI mode) (EXTEND) — **DONE 2026-07-25** (impl-claudecode-aiclient · tip `2ca3154` — App XOR Human dual; `APP` chip green/`ok`+bold+reverse; MANUAL warn+bold+reverse; SPECTATE muted/plain; strict `is False` App gate; `play.attached` plumbed; vocabulary AST gate; App **wire-UNREACHABLE** until 061)
- **Depends-on:** 030 frame · 055/056 seat labels (already LIVE)
- **Live state:** **LIVE** — `cockpit/control_seat.py` `APP_LABEL` / `compose_control_strip_segments` · `screens.py` / `draw.py` tone wiring · `app.py` `play.attached` · vocabulary gate + matrices.
- **Accept:** Control strip can show **App** (green/`ok`) XOR **Human** (warn/MANUAL) as the dual; Spectate remains non-member muted label when not dual-driving; **zero** `AI-PILOT` / `ai_pilot` UI strings in product paths; teach-overlay indicator (if stubbed) is separate from dual.
- **Proof:** Layer-A composer unit (label selection matrix) · `rg` gate no `ai_pilot`/`AI-PILOT` under `tw2002_aiclient/` · optional pty chip text.
- **Hazards:** Do not unify Spectate into the dual. Do not rewrite `control_seat` signature unless proven necessary — extend alongside 056 pattern.

### PWO-061 — Mode switch App↔Human (BUILD) — **KERNEL DONE** + **061-ENTRY GO** (Max Batch 1b CLOSED 2026-07-25)
- **Depends-on:** 060 · 056 (attach already Spectate→Human)
- **Live state:** **PARTIAL** — App-hold→`M`→Human **LIVE** (kernel); Spectate→Human via bare `M` **LIVE** (056); Human→App **MISSING** until Ctrl-A product. Full WO **not CLOSED**.
- **Max Ruled (Batch-1 + 1b · Pending signed canon prose):** Mode chord = **Ctrl-A**; attached bare `M` = TW Move; no single printable may be Mode; migrate Spectate attach off printable `M`.
- **Accept (061-entry):** Ctrl-A toggles App↔Human · attached `M` reaches game · Spectate still reaches Human (via Ctrl-A after migrate) · suite green · tip inventory honest.
- **Proof:** FakeClient/lock + chip flips + Move passthrough pin · Push waits Accept.
- **Hazards:** Do not steal 057 Ctrl-]. Do not loosen no-send tripwire. Esc≠detach.

### PWO-062 — Autopilot/Trainer arm UI (EXTEND)
- **Depends-on:** 060 · 020 daemon
- **Accept:** Arm/disarm taught autopilot is **separate** from actor badge; ON/OFF + write-back visible; no silent arm.
- **Proof:** FakeClient/status round-trip · TTY indicator.
- **Hazards:** Arm ≠ take Human lock.

### PWO-063 — Confirm-to-arm dialog (BUILD)
- **Depends-on:** 062
- **Accept:** Arm requires explicit confirm (danger+reverse per visual-language); bare Enter does not fire.
- **Proof:** Layer-A dialog compose · key matrix (y/N) · no silent arm inject.
- **Hazards:** Loudest palette combo reserved for money/turns risk — match mode-line canon.

### PWO-064 — STOP banner from reason codes (BUILD)
- **Depends-on:** 060 · 020
- **Accept:** STOP shows **typed** reason codes from control-and-escalation catalog only (no free-text invention); chip→Human; A/R/T affordances visible at halt (may stub wires until 066+).
- **Proof:** Inject status/reason fixtures · catalog coverage table · no unknown code renders as invented prose.
- **Hazards:** Banner claims height ahead of optional panels; do not recolor GAME cells.

### PWO-065 — Intervention → Human keyboard (HARDEN)
- **Depends-on:** 064 · 061
- **Accept:** STOP hands keyboard to Human (lock/attach or equivalent product path); Human can type; App does not guess-send.
- **Proof:** FakeClient halt→Human · no `do`/`send` from App after STOP · tripwire still green.
- **Hazards:** Distinct from voluntary `M`; do not conflate with Ctrl-] detach.

### PWO-066 — Teach strip A/R/T visible (BUILD)
- **Depends-on:** 060
- **Accept:** Labels/affordances for Analyze / Record / Assign-Trigger shown on mode line / STOP; keys reserved; **not** bound to attach/launch.
- **Proof:** Composer unit · key intent map · grep that `A`≠attach.
- **Hazards:** Archive bound `A`→attach — DOCS WIN, do not revive.

### PWO-067 — `R` Record macro wire (BUILD)
- **Depends-on:** 066
- **Accept:** Human-init record captures keystrokes to macro store/ledger; no live AI drive.
- **Proof:** FakeClient record start/stop · file/ledger artifact · secret redaction on capture path.
- **Hazards:** Secrets doctrine; never log passwords.

### PWO-068 — `T` Assign-trigger scaffold (BUILD)
- **Depends-on:** 066
- **Accept:** Bind current screen→macro stub (when+guards scaffold); does not auto-fire; no live drive.
- **Proof:** Unit schema round-trip · stub not in live autopilot fire path.
- **Hazards:** Full rule engine is Phase 6 — scaffold only.

### PWO-069 — `A` Analyze on-demand only (BUILD)
- **Depends-on:** 066
- **Accept:** Analyze requires explicit press; never auto-fires on STOP alone; teach-overlay indicator while open.
- **Proof:** No Analyze without key · overlay show/hide · AI never `send`.
- **Hazards:** Teacher is spectator-only (`ai-teacher.md`).

### PWO-070 — Analyze draft → human approve (BUILD)
- **Depends-on:** 069
- **Accept:** Draft rule/macro is not live until human approval gate; rejection drops draft.
- **Proof:** Draft≠fire · approval gate unit · ledger attribution App-after-approve only.
- **Hazards:** Doctrine — human approves before App playback.

### PWO-071 — Operate-the-app cluster (N5) (BUILD)
- **Depends-on:** 060
- **Accept:** Pause/resume/stop taught run controls work; occupy reserved control-strip slot without clobbering liveness (055 collision policy).
- **Proof:** Intent keys · FakeClient arm state · liveness-priority layout pin.
- **Hazards:** N5 ≠ mode badge; do not steal SPECTATE/MANUAL slot under pressure incorrectly.

### PWO-072 — Coverage meter strip (BUILD)
- **Depends-on:** 060 · 025 ledger
- **Accept:** App-vs-Human live share; `?` if unknown; **no live AI slice** in denominator (coverage-metrics / mode-line divergence closed).
- **Proof:** Unit meter math · fixture shares · grep no `AI` live term in meter string.
- **Hazards:** Teaching-provenance axis (if shown) labeled separate from live share.

---

## 3. Depends-on graph (execute order)

```
Phase4 (055–057 LIVE)
        │
        ├─► 060 (App/Human badges; kill AI-PILOT UI)
        │      ├─► 061 (M App↔Human) ─────► 065 (with 064)
        │      ├─► 062 ─► 063 (arm + confirm)
        │      ├─► 064 (STOP banner) ─► 065
        │      ├─► 066 (A/R/T visible)
        │      │      ├─► 067 (R)
        │      │      ├─► 068 (T)
        │      │      └─► 069 ─► 070 (A → approve)
        │      ├─► 071 (N5)
        │      └─► 072 (coverage meter)
        │
Pending (not blocking PREP Accept): DOC-GAP-M-FROM-SPECTATE · DOC-GAP-POST-DETACH-COPY · HARDEN-ATTACH-SOCKET-TIMEOUT
```

**Suggested first execute after PREP Accept:** **060** (badge foundation) — unblocks almost everything; 061 can follow once App chip exists.

---

## 4. Hazards / mid-frame collision

1. **Do not invent Phase-5 product scope** beyond ULTRACODE 060–072 + canon cites above.
2. **Spectate ≠ dual member** — chip may show SPECTATE when observing; `M` dual is App↔Human only once App can drive.
3. **Tripwire** — any new send sites need precise allowlist adjudication; never loosen `test_spectate_no_send.py`.
4. **F2 / G2–G4 HOLD** — no ops spectate CLI, no menu crawler.
5. **North-star unsigned** — no edits to parked one-cockpit draft / `north-star.md` without Max.
6. **Archive badge vocabulary** — AI-PILOT / AUTO-LOOP / AI meter slice are recorded divergences to close, not revive.
7. **Socket hang harden** remains banked — out of Phase-5 PREP execute unless hub assigns.

---

## 5. Execute readiness

**PWO-060 DONE** (`2ca3154`). **PWO-061 KERNEL DONE** (`d4a8829`) — App→Human proven; **Batch 1b CLOSED** (Mode=Ctrl-A; attached `M`=Move) — product HANDOFF to CC `WO-P5-061-ENTRY`. Remaining 062–072 still PREP until hub HANDOFF. Do **not** claim full 061 CLOSED until entry tip lands. Cursor docs lane: OKF status-truth only; no product code in this tick.
