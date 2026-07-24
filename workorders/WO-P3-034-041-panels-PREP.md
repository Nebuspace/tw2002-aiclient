# WO-P3-034…041 — Trainer-cockpit panels · PREP

> Status: **PREP** (Phase 3 · authored 2026-07-24 on Cursor · **product execute is Fable-gated on CC**)
**Phase:** 3 · **Type:** PREP (inventory + tightened Accept/Proof) · **Seat:** `impl-aiclient-cursor`
**Model (execute):** Fable on `impl-claudecode-aiclient` after PWO-031…033 frame lands
**Canon:** `canon/surfaces/trainer-cockpit.md` · `canon/surfaces/visual-language.md` · `canon/engine/priority-engine.md` · `canon/engine/trace-ledger.md` · coaching surfaces as cited
**Refs:** `workorders/ULTRACODE-WO-INVENTORY.md` rows 170–177 · `WO-P3-030-033-cockpit-frame-PREP.md` (shape) · D1 helpers `49b21a1` · tip base `1fd316b`

Authored from a 3-lane read-only fan-out (panels/ledger · HUD/fold/colors · depends/gates). **No product edited.** Ignore CC untracked `cockpit/**` / dirty `screens.py` WIP — live-state below is **committed tip** only.

---

## 0. Strategic framing (absorb before execute)

- **Tip (`1fd316b`) play shell is still a placeholder** — Esc→launcher proven (PWO-030 @ `baa2779`); no live GOALS/FOCUS/HUD/LOGS panels in the committed tree.
- **Frame host is PWO-031…033 (CC·Fable mid).** Panel WOs bind into the three-column body + `[LOGS]` band once that frame is on origin. Do **not** extend the launcher as the panel host (same rule as frame PREP §0).
- **Archive is reference-only** (`archive/` gitignored). Port patterns from archived `compose_play_panels` / `compose_hud_cells` / `format_freshness` / `format_tx_readout` / `hud_seed.py` / `spectate_layout` — never `import twclient`.
- **AI never live-drives.** Tips/DECISIONS/coach text are **read-only** display; live senders remain `{app, human}` only.
- **D1 harness substrate:** `tests/pty_helpers.py` + `tests/fake_client.py` (`49b21a1`). Layer-B proofs use those — not banked `--ignore`d `test_aiclient_play_panels.py` until rewritten under an owning execute WO.

---

## 1. Per-PWO tightened Accept + Proof

### PWO-034 — GOALS panel live (VERIFY/EXTEND) — **DONE 2026-07-24** (impl-claudecode-aiclient · Fable · `cockpit/goals.py` composer + stacked left-gutter split + 1 Hz `status_provider` wire; gate: Mack CRITICAL Infinity-crash + 15s-freeze fixed, Pixel clean; live cadence proven. Status wire carries no GOALS fields yet — all rows render honest-`?` until state_parser/world-model WOs land.)
- **Depends-on:** 033 · 020 (status/ensure path)
- **Live state (tip):** **MISSING** — PlayShellScreen shows profile metadata + `status_line` only (`screens.py` placeholder); no GOALS compose · no `adapters.compose_play_panels` in reborn `adapters.py`. Archive: `compose_play_panels` + `test_aiclient_play_panels.py` (still `import twclient`, ignored).
- **Accept:** Left-gutter **GOALS** lines refresh from daemon `status` ~1 Hz with readable labels; empty state honest (`—` / `(none yet)`); never vanishes when unknown. Met/partial/unknown/blocked glyphs per `trainer-cockpit.md` GOALS status set (`✓`/`·`/`?`/`⊘`).
- **Proof:** Layer-A — pure compose from fixture `status` dict → exact lines (port archive `compose_play_panels` shape into `tw2002_aiclient`). Layer-B — pty+pyte: `_find_text` for `GOALS` title + a known label; FakeClient/status stub; never `run/twd.sock`.
- **Hazards:** Don't invent a second priority engine; GOALS is Layer-1 status only (`priority-engine.md`). Don't block on ignored archive tests — rewrite onto helpers.

### PWO-035 — FOCUS panel live (VERIFY/EXTEND) — **DONE 2026-07-24** (impl-claudecode-aiclient · Fable · `cockpit/focus.py` ranked-suggestions composer + Layer-2 box retitled FOCUS per canon mock ruling; one shared status-poll/tick; gate: Mack clean + hostile-dunder hardening, Pixel ship-ready. `status["focus"]` wire bridge not built — honest-empty until the priority-engine port lands.)
- **Depends-on:** 034
- **Live state (tip):** **MISSING** (same placeholder).
- **Accept:** **FOCUS** list is distinct from GOALS (suggestions / ranked candidates, not status); labels readable; gated candidates marked `⊘`; never auto-sends keys.
- **Proof:** Layer-A — compose fixture with ≥2 ranked items + one gated → FOCUS lines ≠ GOALS lines. Layer-B — pty titles `FOCUS`/`PRIORITIES` visible when left gutter present (fold tier ≥138).
- **Hazards:** FOCUS displays engine output only — does not *pick* unknown screens (later PWO-088). Collapse-into-DECISIONS at fold <138 is PWO-039's ladder; 035 Accept assumes full/wide tier unless testing fold.

### PWO-036 — DECISIONS / coach tips panel (EXTEND) — **DONE 2026-07-24** (impl-claudecode-aiclient · Fable · `cockpit/decisions.py` composer (★/·/⊘, gate-wins-over-chosen, `["—","Exploring…"]` empty, imperative-denylist) + right-gutter HUD(12h)/DECISIONS stacked split + poll-guard fix (narrow-tier starvation) + Layer-B pty; lean Mack gate clean incl. e2e ESC-injection neutralization. Banked: coaching-engine callout = separate WO vs `coaching-engine.md`; world-model→DECISIONS metrics when ported; `ev_cr_per_turn`≠`ev_per_turn` upstream split documented — do not silently unify.)
- **Depends-on:** 033 · 020
- **Live state (tip):** **MISSING**.
- **Accept:** DECISIONS / coach tips render read-only reasoning (`★` chosen · `·` other · `⊘` gated); **tips never send**; empty = `["—", "Exploring…"]` (or equivalent honest empty). No AI-drives badge (D5).
- **Proof:** Layer-A — compose from fixture `autopilot_trace` / coach payload. Layer-B — pty text visible; static assert no send path from panel key handler (tips are display-only).
- **Hazards:** Coaching copy must not look like a live driver. Intervention/STOP strip height priority stays ahead of tips (frame PREP geometry guard #6 / Phase 5).

### PWO-037 — HUD freshness markers (BUILD) — **DONE 2026-07-24** (impl-claudecode-aiclient · Fable · `cockpit/hud.py` pure composer (`compose_hud_cells` 5-field × label/value stride, `format_freshness`, `FRESHNESS_STALE_S=20.0`, sticky-unknown `-` per canon cold-start — NOT the sibling em-dash; non-finite age → unknown-not-stale) + `cockpit/draw.py` public `draw_lines_attrs` (per-line attr through the same clip/sanitize choke point; `draw_lines` delegates — added after a review-caught bypass reintroduced the CJK/escape draw hazards) + screens wire off the shared one-poll snapshot, stale→A_DIM. Poll-guard extended to right_gutter as LATENT hardening only — exhaustive probe: no reachable tier drops DECISIONS while HUD survives; synthetic-tier proof, not a live-bug fix. Mack full-vector clean (mixed CJK+CSI, 8-bit C1, OSC, numeric abuse, one-poll sweep, delegation regression, Esc under hostile load; ZWJ truncation = pyte oracle quirk, product exonerated). pyte can't model SGR-2 → dim proven by fake-stdscr attr capture (pre-declared Accept swap). Banked: `hud_seed` cold-join probe = sibling WO gated on the state_parser/tracked-model port; `status["hud"]` wire bridge not built — honest all-`-` until then.)
- **Depends-on:** 033
- **Live state (tip):** **MISSING** — no `compose_hud_cells` / `format_freshness` / `hud_seed` in reborn package. Glyph table has `freshness_mark` in `session/terminal.py` only. Launcher already has `_SEMANTIC_COLORS` (7-tone) for picker rows — not HUD cells.
- **Accept:** HUD cells persist last-known values with `✦ Ns ago` / `✦ now` (ASCII `*`); dim past stale threshold (canon ~20s / `FRESHNESS_STALE_S`); live values from corrected current screen → tracked model only — **ledger is never read back as live HUD** (`trainer-cockpit.md` N4/N8).
- **Proof:** Layer-A — `format_freshness` + compose cells ages. Layer-B — pty cell attrs dim when age ≥ stale; labels `CREDITS`/`SECTOR`/`TURNS`/`CARGO`/`PROFIT` order.
- **Hazards:** Cold-join seed (`hud_seed`) may be a sibling WO or fold-in — call out if deferred. Don't wire ledger→HUD.

### PWO-038 — TX / liveness strip (BUILD)
- **Depends-on:** 031
- **Live state (tip):** **MISSING** — no TX readout / heartbeat glyph on play chrome.
- **Accept:** A visible “not frozen” signal (heartbeat / TX glyph moves or period advances per `HEARTBEAT_PERIOD_S` / liveness catalog in visual-language); secrets never appear (redaction sink).
- **Proof:** Layer-A — `format_tx_readout` (or reborn twin) from ages. Layer-B — two pty captures separated by >period show glyph/phase change; never `run/twd.sock`.
- **Hazards:** Don't confuse with Mode-line N5 exit-confirm. Spinner must not burn CPU (decouple from viewport fps — frame PREP guard #5).

### PWO-039 — Responsive fold (BUILD)
- **Depends-on:** 031 (geometry) · shares ladder with 033
- **Live state (tip):** **MISSING** on committed play shell. (CC WIP may land `cockpit/layout.py::frame_layout` — execute must verify against **origin** tip after 031–033 Accept, not local dirty.)
- **Accept:** Width tiers never h-scroll: full≥154 · wide-right≥138 · narrow-right≥118 (GOALS+FOCUS fold **into** idle DECISIONS) · minimal≥82 · no_border≥60 · refuse<60. Below 138, status+suggestions survive inside DECISIONS — they do not vanish.
- **Proof:** Layer-A primary — `frame_layout` mode + region x/w at each boundary (mirror frame PREP §PWO-033). Layer-B — pty resize/narrow run: left gutter gone, DECISIONS still shows folded GOALS/FOCUS content, nothing past `max_x-1`.
- **Hazards:** Canon `[CODE NOTE]` vs constants — prefer constants 154 (D4). Collision: CC owns layout until STATUS — this PREP must not edit `cockpit/**`.

### PWO-040 — Semantic chrome colors (POLISH)
- **Depends-on:** 031
- **Live state (tip):** **PARTIAL** — launcher `_SEMANTIC_COLORS` 7-tone table exists (`screens.py` ~38–54) for profile rows; play/cockpit chrome does not yet apply `status_semantic` / `gauge_semantic` / mode badges. Archive classifiers in `spectate_layout`.
- **Accept:** One 7-tone table drives cockpit chrome (ok/warn/danger/…); warn/danger/ok on gauges + status; `TW2002_ASCII=1` loses zero information; **no** `ai_pilot` badge (D5).
- **Proof:** Layer-A — tone→attr map + classifier unit tests. Layer-B — pty cell `.fg` / `.bold` for warn vs ok fixtures (never ANSI-regex).
- **Hazards:** Game viewport stays server CP437 palette — semantic set is chrome-only (`visual-language.md`).

### PWO-041 — LOGS band (EXTEND)
- **Depends-on:** 031 · 020
- **Live state (tip):** **MISSING** (placeholder has no `[LOGS]` band). Ledger module not ported (`session/daemon.py` comments defer ledger).
- **Accept:** Full-width `[LOGS]` transcript tail; lines appear as session advances; **redacted** (passwords never shown); newest row flash OK per canon.
- **Proof:** Layer-A — redaction unit + tail compose. Layer-B — pty `_find_text` for `LOGS` + a non-secret line; secret fixture asserts redaction marker, never raw password.
- **Hazards:** Public-repo / secrets doctrine. Trace-ledger schema may be thin stub first — Accept requires redacted tail, not full Phase-9 ledger.

---

## 2. Depends-on graph (execute order)

```
031 (frame) ─┬─► 032 (strip) ─► 033 (columns)
             ├─► 038 (TX/liveness)
             ├─► 039 (fold — often same commit as 033 layout)
             ├─► 040 (semantic colors polish)
             └─► 041 (LOGS band) ── needs 020 status/log path
033 ─┬─► 034 (GOALS) ─► 035 (FOCUS)
     ├─► 036 (DECISIONS/tips)
     └─► 037 (HUD freshness)
```

**Hard gate:** no 034–041 product execute until **031–033 CLOSED on origin** (or hub explicitly slices a panel that is pure Layer-A against landed `cockpit/layout.py` only).

---

## 3. Fable-execute gates

| Gate | Rule |
|------|------|
| Seat/model | Product TUI execute = **CC · Fable** (Phase 3–5 carve-out). Cursor may PREP/docs/non-UI only unless Max reassigns. |
| Frame first | 031–033 Accept+push before panel chrome-wire into `PlayShellScreen`. |
| Esc invariant | Preserve PWO-030 Esc→`"back"` + ADR-001 daemon-survival (`baa2779` stay-green). |
| D5 | No `ai_pilot` / AI-drives badge. |
| D6 | No exit-confirm popup (Phase 5 / mode-line N5). |
| Proof stack | Layer-A pure compose/layout · Layer-B `tests/pty_helpers` + `fake_client` · path-leak green · scoped commits. |

---

## 4. Layer-A / Layer-B proof plan (shared)

- **Layer A:** reborn pure helpers under `tw2002_aiclient/` (e.g. `cockpit/panels.py`, `hud.py`, or adapters compose) — assert strings/regions; no curses.
- **Layer B:** `tests/pty_helpers.capture_pty*` / `pyte_grid` / `find_text` / cell attrs; `pty_curses_supported` skip-guard; scripted status via FakeClient or monkeypatched ensure/status — **never** `run/twd.sock`.
- **Never ANSI-regex** (frame PREP §2).
- Banked archive suites (`test_aiclient_play_panels`, `test_hud_seed`, `test_ledger`, …) stay `--ignore` until an execute WO rewrites them onto `tw2002_aiclient`.

---

## 5. Hazards / mid-frame collision

1. **CC dirty tree** — `cockpit/**`, `screens.py`, `tests/test_cockpit_*.py` may be mid-flight. PREP authors must not scoop or “fix forward” those paths.
2. **Live-state drift** — after 031–033 lands, re-read tip before panel execute; update this PREP’s “MISSING→PARTIAL” markers in the execute WO, not by editing product here.
3. **Ignored tests** — false confidence from archive fixtures; Prefer new `tests/test_cockpit_panels_*.py`.
4. **Ledger absence** — 041 may need a thin redacted ring-buffer before full trace-ledger port.
5. **Secrets** — LOGS + any status dump: redaction sink mandatory.

---

## 6. Execute readiness

All of **034–041 = PREP only** on this seat. Build-wave is **Fable-gated on CC** after frame CLOSE. Next Cursor value (if idle): materialize per-PWO EXECUTE stubs when hub feeds them, or stay clear during CC chrome-wire.
