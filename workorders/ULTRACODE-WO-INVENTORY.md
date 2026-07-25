# Ultracode WO inventory — Orchestrator review draft

**REVISED greenfield-clean per WO-ULTRACODE-ADOPT (Max GO 2026-07-23). This file is the MASTER LIST.**

**Date:** 2026-07-23  
**Repo:** `tw2002-aiclient` (clean root: `canon/` · `workorders/` · `archive/`)  
**Status:** PROPOSAL — do not treat as the live queue until Orchestrator reviews/approves  
**Prior queue:** `workorders/WO-00`…`WO-17` (product-surface oriented; partially stale post-root archive)

---

## 1. Executive verdict

| Dimension | Assessment |
|-----------|------------|
| Current WO-00…17 quality | **Good surface slice** — clear Goal/Accept/Proof, UI-first ordering, honest verify-vs-build labels |
| Canon coverage | **Surfaces ~40%**; **architecture/engine/strategy/doctrine ~10%** — almost entirely missing as WOs |
| Critical freshness bug | After Max’s root cleanup, WO Proof paths assume `./tw2002-aiclient`, `twclient/`, `config/`, `tests/` at **repo root**. Those now live under `archive/pre-rebirth-2026-07-23/`. Early WOs are stale; the fix is a **greenfield rebuild from `canon/`** — `archive/` is reference only, never restored to root |
| Philosophy fit | Early verify chain is right; WO-11 (viewport) is the only “fat” build; teach/escalation/`M`/confirm-gate under-split |
| Proposed expansion | **78 PWOs** across 9 phases (below) — Orchestrator can accept, cut, or merge |

**Bottom line:** Keep the *shape* of WO-00…17, but (1) insert a **Phase 0 greenfield scaffold**, (2) split cockpit/mode/teach into thinner verifiable chunks, (3) add full **engine + doctrine + strategy** WO streams that the current set never attempted.

---

## 2. Critique of current WO-00…17

| WO | Type | Verdict | Issue |
|----|------|---------|-------|
| 00 | verify | Keep · rewrite paths | Root archive broke Proof; needs bootstrap dependency |
| 01 | verify | Keep · rewrite | Same; still best “see UI” target *after* code returns to root |
| 02 | verify | Keep · rewrite | Password-never-on-form is canon-correct |
| 03 | verify | Keep | Chrome-only path good |
| 04 | verify | Keep · split | Bundle ensure + run-dir policy; login stuck/`game_select` needs own WO |
| 05 | verify | Keep · rename later | “Autopilot” badge vs canon App arm-confirm — file finding, don’t conflate |
| 06 | verify | Keep · thin | Pre-cockpit panels only |
| 07 | verify | Keep | Good; expand reason-code catalog coverage later |
| 08 | verify | Keep | Attach path; separate spectate-only WO missing |
| 09 | extend | Keep | World-identity strip |
| 10 | build | Keep · maybe split | Frame vs fold breakpoints |
| 11 | build | **Too fat** | Split: subscribe stream · render grid · color parity · disconnect chrome |
| 12 | extend | Keep | Logs band |
| 13 | extend | Keep · incomplete | Missing dedicated **`M` toggle** WO |
| 14 | build | Under-scoped | A/R/T should be 3+ WOs (scaffold · record wire · analyze wire · assign-trigger) |
| 15 | polish | Keep | Depends on ui-polish now archived under tooling — cite canon surface polish sections |
| 16 | extend | Keep | Bank boundary |
| 17 | build | Keep · late | Needs ledger actor attribution first |

**Overlaps:** 05 vs 13 (toggle vs actor badge); 07 vs STOP banner in mode-line canon; 06 vs cockpit GOALS/FOCUS ownership.

**Missing vs UI-first philosophy:** no WO for confirm-to-arm dialog; no spectate-as-product-pane; no fold/collapse; no TX/liveness “is it frozen?” strip. (Under greenfield, "restore product package to root" is not a gap — see PWO-003.)

---

## 3. Canon coverage matrix

Legend: **C** = covered by current WO · **P** = partial · **M** = missing from WO set

### Architecture
| Concept | Cov | Notes |
|---------|-----|-------|
| North Star | P | Implied; no WO asserts findings discipline |
| Control & Escalation | P | 05/07/13/14 touch; `M`, reason catalog, confirm-gate **M** |
| Session Engine | P | 04; control-lock / actor tag WOs **M** |
| CLI Verb Surface | P | 00; full verb audit **M** |
| Settle Detection | M | |
| Rule–Macro Engine | M | |
| APP Autopilot Model | P | 05; stop-on-unknown loop / arm-confirm **M** |
| Login Automaton | P | 04; NEW/RETURNING / game_select recovery **M** |
| Resilience & Reconnect | M | |

### Surfaces
| Concept | Cov | Notes |
|---------|-----|-------|
| Entry & Profile Selection | C/P | 01–02, 09, 16 |
| Trainer Cockpit | P | 03,06,10–12,15,17; viewport/HUD freshness/fold **M**/partial |
| Mode Line & Teach | P | 13–14; `M`, confirm-gate, operate-app cluster **M** |
| Spectate & Attach | P | 08 attach; dedicated spectate product surface **M** |

### Engine
| Concept | Cov | Notes |
|---------|-----|-------|
| Screen Understanding | M | |
| World Identity | P | 09 |
| World Model | M | |
| Game-Data Store | M | |
| Menu Map & Introspection | M | |
| Trace Ledger | P | 12; actor attribution **M** |
| Macros | P | 14 scaffold only |
| AI Teacher | P | 14 Analyze stub |
| Candidate Mining | M | |
| Auto-Haggle | M | |
| Priority Engine | P | 06 GOALS/FOCUS consume; engine itself **M** |
| Coaching Engine | M | |
| Coverage Metrics | P | 17 |

### Strategy
| Concept | Cov | Notes |
|---------|-----|-------|
| Trade Loops & Chains | M | |
| Port Economics | M | |
| Exploration Policy | M | |
| Toll & Defense | M | |
| Planet Colonization | M | |
| Special Formations | M | |
| Ship Progression | M | |

### Doctrine
| Concept | Cov | Notes |
|---------|-----|-------|
| Alignment & Conduct | P | 16 boundary text only |
| Secrets & Credentials | P | 02 password-off-form; redaction/rotation WOs **M** |
| Action-Safety Guards | M | |

---

## 4. Proposed phased catalog (PWO-xxx)

Each entry: **ID · Title · Phase · Type · Depends · Goal · Accept (short) · Proof hint · Canon**

Types: `bootstrap` · `verify` · `build` · `extend` · `harden` · `docs-finding`

### Phase 0 — Greenfield scaffold (code does not exist at root today; archive is reference-only)

**RESOLVED: greenfield.** Max ruled greenfield-from-`canon/` over restore-from-`archive/` (2026-07-23) — the restore-vs-greenfield decision that was PWO-001 is closed and is not carried forward as an executable PWO. **PWO-003 is the Phase-0 spine/head** — the greenfield package scaffold — with everything else in this phase depending on it.

| ID | Title | Type | Depends | Goal | Accept | Proof | Canon |
|----|-------|------|---------|------|--------|-------|-------|
| PWO-000 | Inventory archive tree — **REFERENCE-ONLY** | docs-finding | — | Document what lives under `archive/pre-rebirth-2026-07-23/` for lookup only; never a recommendation driver or a restore-to-root step | README inventory matches ls | `ls archive/pre-rebirth-…/{code,config,runtime}` | north-star |
| PWO-003 | Greenfield package scaffold — **Phase-0 spine** | bootstrap | 000 (reference only) | Create empty `tw2002_aiclient` + `twclient` stubs matching session-engine split, built fresh from canon | `python -m tw2002_aiclient` TTY-gates | non-TTY exit 2 | session-engine |
| PWO-004 | Dev seat smoke (rewrite WO-00) | verify | 003 | Seat runnable | help + TTY gate | as WO-00 | cli-verbs |
| PWO-005 | Config + secrets layout | bootstrap | 003 | `config/profiles.toml.example`, `servers.toml`, secrets discipline | example loads; secrets never in profiles | pytest or manual | secrets-and-credentials |
| PWO-006 | Finding log stub | docs-finding | 004 | DOCS-WIN findings file for known divergences (`ai_pilot`, etc.) | `canon-findings.md` or section in log | file exists | north-star conventions |

### Phase 1 — Entry surface (see UI early)

| ID | Title | Type | Depends | Goal | Accept | Proof | Canon |
|----|-------|------|---------|------|--------|-------|-------|
| PWO-010 | Launcher smoke | verify | 004 | See branded launcher | navigate + quit | TTY | entry-and-profile-selection |
| PWO-011 | Launcher empty / broken states | build | 010 | Empty list + corrupt profile rows | empty CTA; broken dim+reason | TTY + fixture | entry… panel states |
| PWO-012 | Create profile form | verify/build | 010 | Catalog server + no password field | save section sans password | TTY + grep toml | entry… new-player |
| PWO-013 | Create form validation | harden | 012 | Invalid fields fail loud | bad id/game rejected | TTY | entry… |
| PWO-014 | World identity on launcher rows | extend | 010 | host·game·character columns | strip matches world-id | TTY | world-identity · entry… |
| PWO-015 | Player bank touchpoint | extend | 010 | Bank list + no-collusion line | `b` or footer; no secrets | TTY + `tw players list` | entry… rotation |
| PWO-016 | Hand-off to cockpit | verify | 010 | Enter → play shell | Esc returns launcher | TTY | entry… hand-off |
| PWO-017 | Launcher color/glyph polish | polish | 010 | Canon launcher palette | retired/active glyphs | TTY | entry… visual · visual-language |

### Phase 2 — Session wire (daemon)

| ID | Title | Type | Depends | Goal | Accept | Proof | Canon |
|----|-------|------|---------|------|--------|-------|-------|
| PWO-020 | Ensure from play entry | verify/build | 016 | Ensure reaches command class | status ok + sock | TTY+status | login-automaton · session-engine |
| PWO-021 | Run-dir default policy | harden | 020 | Default `run/` only; env override documented | no surprise `run/<profile>` | status path | session-engine |
| PWO-022 | Ensure `--no-auto-arm` | harden | 020 | Ensure never surprise-arms trainer | AP off after ensure flag | status | app-autopilot-model |
| PWO-023 | Login NEW vs RETURNING | harden | 020 | Branches over secure store | both paths proven | live or fixture | login-automaton |
| PWO-024 | Game-select recovery | harden | 020 | Stuck `game_select` recoverable | reach main_command | `tw do` / ensure | login-automaton |
| PWO-025 | Control-lock + actor tag **PARTIAL** — lock+`VALID_SENDERS` LIVE; **LedgerWriter / attach ledger MISSING** (`daemon.py` deferred) | harden | 020 | Every send tagged `{app,human}` | ledger rows actor∈{app,human} | ledger sample | control-and-escalation · trace-ledger |
| PWO-026 | Settle detection baseline | verify/harden | 020 | Prompt/idle/timeout settle | no false ready | unit+live | settle-detection |
| PWO-027 | Reconnect + login replay **DONE** 2026-07-24 (`e1f189c` · SessionGuardian D9) | build | 020 | Drop sock recovers | spectate/play survive recycle | stop sock / kill | resilience-and-reconnect |
| PWO-028 | Idle keepalive off on unsafe **DONE** 2026-07-24 (`4db92a1` · D10 `main_command`-only) | harden | 027 | Keepalive suppressed on unsafe screens | no keepalive on Option? | test | resilience… |

### Phase 3 — Trainer cockpit frame

| ID | Title | Type | Depends | Goal | Accept | Proof | Canon |
|----|-------|------|---------|------|--------|-------|-------|
| PWO-030 | Play chrome navigation | verify | 016 | Esc↔launcher | clean return | TTY | trainer-cockpit |
| PWO-031 | Outer border frame | build | 030 | Bordered regions | no overlap ≥80×24 | TTY resize | trainer-cockpit |
| PWO-032 | Character strip | extend | 031·014 | Top identity strip | host/game/char | TTY | trainer-cockpit |
| PWO-033 | Three-column body scaffolding | build | 031 | GOALS \| center \| HUD slots | labeled empty ok | TTY | trainer-cockpit |
| PWO-034 | GOALS panel live **DONE** tip `f594b9e` | verify/extend | 033·020 | GOALS from status | updates ~1Hz | TTY | trainer-cockpit · priority-engine |
| PWO-035 | FOCUS panel live **DONE** tip `f594b9e` | verify/extend | 034 | FOCUS distinct from GOALS | labels readable | TTY | trainer-cockpit |
| PWO-036 | DECISIONS / coach tips panel **DONE** tip `f594b9e` | extend | 033·020 | Tips never send | read-only | TTY | coaching-engine |
| PWO-037 | HUD freshness markers **DONE** tip `f594b9e` | build | 033 | stale/fresh tones | age visible | TTY | trainer-cockpit HUD |
| PWO-038 | TX / liveness strip **DONE** tip `f594b9e` | build | 031 | “not frozen” signal | heartbeat glyph moves | TTY | trainer-cockpit liveness |
| PWO-039 | Responsive fold **DONE** tip `f594b9e` | build | 031 | Collapse order per canon | no overlap small term | TTY resize | trainer-cockpit fold |
| PWO-040 | Semantic chrome colors **DONE** tip `f594b9e` | polish | 031 | 7-tone table | warn/danger/ok | TTY | mode-line · cockpit polish · visual-language |
| PWO-041 | LOGS band **DONE** 2026-07-24 (own commit, first past `61c1012`) | extend | 031·020 | Ledger tail redacted | lines appear | TTY + log | trace-ledger · cockpit |

Banked hygiene (not a PWO id): **pty mid-flush settle** — PREP `workorders/WO-PTY-SETTLE-HYGIENE-PREP.md` (shared `settle_drain`; KEY_RESIZE separate).

### Phase 4 — Game viewport & watch surfaces

| ID | Title | Type | Depends | Goal | Accept | Proof | Canon |
|----|-------|------|---------|------|--------|-------|-------|
| PWO-050 | Watch-stream subscribe **DONE** 2026-07-24 (own commit, first past `861ea58`) | build | 020 | Product reads settle stream | frames arrive | unit/live | spectate-and-attach |
| PWO-051 | Center 80×25 viewport shell **DONE** 2026-07-24 (own commit, first past `b211be2`; grown `bb780e0`) | build | 033·050 | Empty bordered 82×27 | geometry | TTY | trainer-cockpit GAME UI |
| PWO-052 | Viewport render grid **DONE** 2026-07-24 (`de47a26` · mono glyph; color → 053) | build | 051 | pyte cells drawn | matches spectate | side-by-side | spectate-and-attach color · visual-language |
| PWO-053 | Viewport color parity **DONE** 2026-07-25 (`eb59274`) | harden | 052 | Color map == ops spectate | visual/diff | TTY | spectate… N3 · visual-language |
| PWO-054 | Disconnect viewport chrome **DONE** 2026-07-25 (`6c7d834`) | build | 051 | Warn/danger border when down | state visible | kill sock | trainer-cockpit states |
| PWO-055 | Product spectate mode (read-only) **DONE** 2026-07-25 (`37b3e99` · F2 ops CLI HOLD) | build | 050 | Watch without lock | no sends | TTY | spectate-and-attach · visual-language |
| PWO-056 | Attach from cockpit **DONE** 2026-07-25 (`2c2decc` · `M`) | verify/build | 020 | `M` attach takes lock | Human badge | TTY | spectate-and-attach |
| PWO-057 | Detach returns App/Spectate path **DONE** 2026-07-25 (`bba53d4` · Ctrl-]) | verify | 056 | Ctrl-] / detach | lock released | TTY | control-and-escalation |

### Phase 5 — Mode line, escalation, teach

> PREP: `workorders/WO-P5-060-072-mode-teach-PREP.md` — Phase 4 CLOSED; **PWO-060 DONE** (`2ca3154`); **PWO-061 KERNEL DONE** (`d4a8829` · App→Human via `M`; Human→App **PARKED** Max B′/C); A·R·T / STOP / N5 / coverage still MISSING.

| ID | Title | Type | Depends | Goal | Accept | Proof | Canon |
|----|-------|------|---------|------|--------|-------|-------|
| PWO-060 | App/Human badge (no AI mode) **DONE** 2026-07-25 (`2ca3154` · App XOR Human · strict gate) | extend | 030 | Dual only | no `ai_pilot` UI string | grep+TTY | mode-line-and-teach-controls |
| PWO-061 | `M` mode switch — **KERNEL DONE** 2026-07-25 (`d4a8829` · App→Human; Human→App PARKED Max) | build | 060·056 | Toggle App↔Human | lock flips | TTY | control… Mode Switch |
| PWO-062 | Autopilot/Trainer arm UI — PREP | extend | 060·020 | Separate from actor badge | ON/OFF + write-back | TTY | app-autopilot-model |
| PWO-063 | Confirm-to-arm dialog — PREP | build | 062 | Arm requires explicit confirm | no silent arm | TTY | mode-line confirm-gate |
| PWO-064 | STOP banner from reason codes — PREP | build | 060·020 | Typed labels only | catalog coverage | inject status | control… catalog |
| PWO-065 | Intervention → Human keyboard — PREP | harden | 064·061 | STOP hands control | Human can type | live halt | control… escalate |
| PWO-066 | Teach strip A/R/T visible — PREP | build | 060 | Affordances shown | labels present | TTY | mode-line A/R/T |
| PWO-067 | `R` Record macro wire — PREP | build | 066 | Human-init record | macro file/ledger | TTY+cli | macros |
| PWO-068 | `T` Assign-trigger scaffold — PREP | build | 066 | Bind screen→macro stub | no live drive | TTY | rule-macro-engine |
| PWO-069 | `A` Analyze on-demand only — PREP | build | 066 | Never auto-fires | press required | TTY | ai-teacher |
| PWO-070 | Analyze draft → human approve — PREP | build | 069 | Draft not live | approval gate | TTY/cli | ai-teacher · doctrine |
| PWO-071 | Operate-the-app cluster (N5) — PREP | build | 060 | Pause/resume/stop taught run | controls work | TTY | mode-line N5 |
| PWO-072 | Coverage meter strip — PREP | build | 060·025 | Taught vs escalation share | `?` if unknown | TTY | coverage-metrics |

### Phase 6 — APP autopilot + rule engine (backend-heavy)

> PREP: `workorders/WO-P6-080-088-autopilot-PREP.md` (tip `5b848f0`) — classify LIVE; state_parser MISSING; 085/086 LIVE gated; 081–084/087–088 MISSING. Do not invent Phase-5 chrome.

| ID | Title | Type | Depends | Goal | Accept | Proof | Canon |
|----|-------|------|---------|------|--------|-------|-------|
| PWO-080 | Screen class + state parse — **PARTIAL** (classify LIVE; state_parser MISSING) | verify/harden | 020 | Settled→{class,state} | fixtures green | pytest | screen-understanding |
| PWO-081 | Guarded rule schema — PREP | build | 080 | when+guards→macro | load/store | unit | rule-macro-engine |
| PWO-082 | Macro capture + replay halt — PREP | build | 067·081 | Divergence halts | test+live | macros |
| PWO-083 | Autopilot loop stop-on-unknown — PREP | harden | 081·064 | Unknown→STOP | no guess send | unit+live | app-autopilot-model |
| PWO-084 | Re-validate every cycle — PREP | harden | 083 | Multi-cycle re-match | halt on drift | unit | app-autopilot-model |
| PWO-085 | Remove/replace MODE_AI_PILOT **LIVE gated** (product; residual test rehab) | harden | 060·083 | Finding closed or mode gone | no live ai sender | grep+tests | control divergence |
| PWO-086 | Actor enum {app,human} only **LIVE** (`VALID_SENDERS`) | harden | 025 | No `ai` live actor | ledger invariant | tests | conventions |
| PWO-087 | Auto-haggle as guarded rule — PREP | harden | 081 | Built-in rule archetype | haggle tests | pytest+live | auto-haggle |
| PWO-088 | Priority engine ranks taught only — PREP | harden | 081·034 | Never picks unknown screens | unit | priority-engine |

### Phase 7 — World stores & learning substrate

| ID | Title | Type | Depends | Goal | Accept | Proof | Canon |
|----|-------|------|---------|------|--------|-------|-------|
| PWO-090 | World-id keying everywhere | harden | 014 | One key scheme | stores colocated | unit | world-identity |
| PWO-091 | World-model persist/read | build | 090·080 | Sector DB grows | files+API | explore tick | world-model |
| PWO-092 | Game-data two-layer store | build | 090 | Semantics≠DATA | no hardcoded stats in product | audit | game-data-store |
| PWO-093 | Menu-map read-only crawl | build | 090 | Never-commit crawler | sacrificial only | crawl | menu-map… |
| PWO-094 | Trace ledger append semantics | harden | 025·041 | Per-dispatch rows | schema | unit | trace-ledger |
| PWO-095 | Candidate mining (no LLM) | build | 094 | Recurring patterns→candidates | dry-run | unit | candidate-mining |
| PWO-096 | Coaching tips read-only | build | 036·091 | Options never act | TTY | coaching-engine |

### Phase 8 — Strategy as taught behaviors (human-approved)

| ID | Title | Type | Depends | Goal | Accept | Proof | Canon |
|----|-------|------|---------|------|--------|-------|-------|
| PWO-100 | Port economics params | build | 092 | Hypothesis-tagged numbers | tags present | unit | port-economics |
| PWO-101 | Trade loop define/rank | build | 100·081 | Credits/turn ranking | unit | trade-loops |
| PWO-102 | Trade loop run + depletion STOP | build | 101·083 | STOP on depletion | live/fixture | trade-loops |
| PWO-103 | Exploration frontier BFS | build | 091·083 | Stops on unknown sector UI | live | exploration-policy |
| PWO-104 | Toll fight/pay/reroute guards | build | 081 | NPC only; combat escalates | unit+live | toll-and-defense |
| PWO-105 | Formations locate/catalog | build | 091 | Recommend only | unit | special-formations |
| PWO-106 | Colonization recommend + Genesis confirm | build | 096 | Genesis human one-shot | TTY confirm | planet-colonization |
| PWO-107 | Ship/holds upgrade recommend | build | 096 | Purchase human-approved | TTY | ship-progression |

### Phase 9 — Doctrine / safety teeth

| ID | Title | Type | Depends | Goal | Accept | Proof | Canon |
|----|-------|------|---------|------|--------|-------|-------|
| PWO-110 | Secrets resolve precedence | harden | 005 | env > secrets file | tests | secrets-and-credentials |
| PWO-111 | Redaction on all send paths | harden | 020 | No password in logs/ledger | scan | secrets… |
| PWO-112 | Action-safety byte guards | harden | 081·083 | Destructive macros blocked | unit | action-safety-guards |
| PWO-113 | Alignment: no PvP aggression rules | harden | 070·081 | Teacher cannot propose PvP harm | unit | alignment-and-conduct |
| PWO-114 | Hypothesis-tag discipline CI | harden | 100 | Untagged numbers fail check | script | conventions |
| PWO-115 | Public-bound lint | harden | — | No personal FQDN/names in canon/WOs | lint | conventions |

---

## 5. Mapping: current WO → proposed

| Current | Maps to |
|---------|---------|
| WO-00 | PWO-004 (+ Phase 0) |
| WO-01 | PWO-010 |
| WO-02 | PWO-012–013 |
| WO-03 | PWO-030 |
| WO-04 | PWO-020–024 |
| WO-05 | PWO-062–063 |
| WO-06 | PWO-034–035 |
| WO-07 | PWO-064 |
| WO-08 | PWO-056–057 |
| WO-09 | PWO-014 · PWO-032 |
| WO-10 | PWO-031 · PWO-033 · PWO-039 |
| WO-11 | PWO-050–054 |
| WO-12 | PWO-041 |
| WO-13 | PWO-060–061 |
| WO-14 | PWO-066–070 |
| WO-15 | PWO-040 · PWO-017 |
| WO-16 | PWO-015 |
| WO-17 | PWO-072 |

---

## 6. Counts

Greenfield resolves the **PWO-002 ⊕ PWO-003** restore/greenfield branch to **PWO-003 only** — PWO-001 (the decision itself) is RESOLVED prose, not a WO, and PWO-002 (restore-to-root) drops entirely. Phase 0 is therefore 6 executable PWOs (000 reference-only + 003–006 build/verify), not 7.

| Phase | PWO count |
|-------|-----------|
| 0 Greenfield scaffold | 6 |
| 1 Entry | 8 |
| 2 Session | 9 |
| 3 Cockpit | 12 |
| 4 Viewport/watch | 8 |
| 5 Mode/teach | 13 |
| 6 Autopilot/rules | 9 |
| 7 Stores/learning | 7 |
| 8 Strategy | 8 |
| 9 Doctrine | 6 |
| **Total** | **86** |

Corrected unique ID count in catalog: **PWO-000, 003–006 (5 executable + 1 reference-only = 6) + 010–017 (8) + 020–028 (9) + 030–041 (12) + 050–057 (8) + 060–072 (13) + 080–088 (9) + 090–096 (7) + 100–107 (8) + 110–115 (6) = 86**, headline **~85 executable** once PWO-000 (reference-only, not a build/verify step) is set aside from the build count.

---

## 7. Recommended Orchestrator actions

1. **PWO-001 is resolved**: Max ruled greenfield-from-`canon/` (2026-07-23) — `archive/` stays reference-only, never restored to root. No further restore-vs-greenfield decision is open; build proceeds from PWO-003 (Phase-0 spine) forward.
2. Mark current `WO-00…17` as **LEGACY-SURFACE** until paths fixed; point README at this inventory.
3. Approve Phase 0–1 as the next live queue (thin files); keep Phase 6–9 as backlog until cockpit viewport exists.
4. Do **not** open all 87 as files yet — materialize Phase 0–2 as real `WO-*.md` after decision; keep this inventory as the master list.
5. File known divergences (`MODE_AI_PILOT`, EV per-cycle driver, `{ai,…}` actors) as findings via PWO-006 before rewriting autopilot.

---

## 8. Top 5 gaps in the *current* set

1. **No bootstrap** after root archive — Proof commands are currently false.  
2. **No `M` / confirm-to-arm / STOP reason catalog** as first-class WOs.  
3. **Viewport under-split** (WO-11 monolith).  
4. **Engine/strategy/doctrine almost absent** — surfaces-only queue cannot reach North Star.  
5. **Teach path under-split** (A/R/T + approve collapsed into WO-14).

---

*End of inventory — for Orchestrator review. Not committed. Not the live execution queue until approved.*
