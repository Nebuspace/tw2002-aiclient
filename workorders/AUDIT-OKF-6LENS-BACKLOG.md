# AICLIENT OKF 6-lens audit backlog

> Seat: `impl-aiclient-cursor` · Tip: `59c4455` (audit drafts) atop `458d140` / product `d4a8829` · UTC: 2026-07-25T05:12Z  
> HANDOFF: `AUDIT-OKF-6LENS` · **No product `.py` in this ticket**  
> HOLDs honored: F2 · G2–G4 · auth/secrets (rotate CLOSED — archive never-live) · **Batch 1b CLOSED** (Ctrl-A Mode) · **Batch 2/3 CLOSED** (APP chip · Spectate≠Mode · Ctrl-]@App-hold no-op · north-star SIGNED · log_note RETIRE)  
> Scout cross-check: inventory tip-map — **064 EXECUTING · 062/066 STAGED** (serialize 064→062→066); staged 063/065/067–072; 061 CLOSED; 080 PARTIAL; **085/086 LIVE** (gated). **Closed since:** HARDEN-ATTACH `88004d8` · WatchHub `00cb9e8` · SAFE-ADDSTR `29fd76c` · GLYPH `8facad9` · SAFE-WIDTH `c0bdab7` · APP-LABEL docs-win · CTRL-]APP Ruled · mux Ctrl-A note · **RECONNECT `19a0a27`** · **CLI-KEYS `032bc12`** · **061-ENTRY `420430d`** · **log_note RETIRE `4280d8a`** · **ENTRY-APP `7c0e882`** · **stale-M `ca1e078`→`276327e`** · **UNICODE-OK `922739b`** · **A-L1-052-TIP**. Banked: session-audit **F6–F8** + classify/coverage gap. Open Max-gated: **F5** · OPEN-003 · F2/G2–G4. CC in flight: 064 ∥ F1.

Committable twin: `workorders/AUDIT-OKF-6LENS-BACKLOG.md`. Draft WOs: `workorders/WO-AUDIT-*.md` (8).

## Already queued (dedup — do not re-WO)

| Bucket | IDs | Notes |
|---|---|---|
| Phase-5 PREP | PWO-062…072 | `WO-P5-060-072-mode-teach-PREP.md` — **064 EXECUTING**; 062/066 STAGED (serialize); 063/065/067–072 staged |
| Pending DOC-GAPs | POST-DETACH-COPY · SPECTATE-REVERSE-VS-PLAIN | `canon/findings.md` — M-FROM-SPECTATE SUPERSEDED · CTRL-RBRACKET **Ruled** · APP chip **Ruled** |
| Banked harden | HARDEN-ATTACH-SOCKET-TIMEOUT | **DONE** tip `88004d8` (CC) · `WO-AUDIT-HARDEN-ATTACH` EXECUTED/DONE |
| Zone-A harden | WATCHHUB-LOOP-CONTAIN | **DONE** tip `00cb9e8` · `WO-AUDIT-WATCHHUB-LOOP-CONTAIN` EXECUTED |
| Zone-A polish | SAFE-ADDSTR / GLYPH | Both **DONE** (`29fd76c` / `8facad9`) · WOs EXECUTED |
| Banked docs | UNICODE-OK-DOCSTRING | **DONE** tip `922739b` (CC · was `3404f81`) · `WO-AUDIT-UNICODE-OK-DOCSTRING` EXECUTED |
| Max-ruled | 061 Accept #2 Human→App | **Batch 1b CLOSED** — Mode=Ctrl-A · attached `M`=Move · no printable Mode · CC product HANDOFF |
| Max-ruled | Batch 2/3 cluster | **CLOSED** — `APP` chip · Spectate≠Mode · Ctrl-]@App-hold no-op · north-star SIGNED · log_note RETIRE · secrets never-live |
| Max-ruled | Entry chip = APP | **DONE** tip `7c0e882` (CC · was `0537298`) — App-hold entry; chip `APP` · `WO-AUDIT-ENTRY-APP-CHIP` EXECUTED |
| Phase 6 tip | PWO-080 PARTIAL · 085/086 LIVE · 081–084/087–088 MISSING | Fold into WO-AUDIT-PHASE6-PREP |
| Orphan archive tests | `tests/test_spectate_app.py` etc. still `import twclient` + AI-PILOT expects | cleanup candidate (not product UI) |
| Banked session-audit | F6–F8 · classify coverage gap | **BANKED** `@ 12:15Z` adjudicate · findings rows · no WO this wave |
| Max-gated session | F5 daemon `internal_error:{e}` | **🧑‍⚖️** DECISION-NEEDED — no WO until Max |

## Findings by lens (net-new / honesty)

### L1 — Features in canon/PREP not built
| ID | P | Gap | Paths | Depends |
|---|---|---|---|---|
| A-L1-052-TIP | P1 | ULTRACODE still says PWO-052 PREP while viewport PREP file stamps DONE | `ULTRACODE-WO-INVENTORY.md` | **CLOSED** — inventory row already **DONE** `de47a26` (no stale PREP claim) |
| A-L1-025-LEDGER | P1 | PWO-025 Accept needs ledger actor tags; daemon still “LedgerWriter deferred” | `session/daemon.py` · future `ledger.py` | 041 partial |
| A-L1-P6-PREP | P2 | Phase 6–9 lack tip-honest PREP like Phase 5 | `workorders/WO-P6-*-PREP.md` (new) | after 061 entry |
| A-L1-062-072 | — | Arm/STOP/A·R·T/N5/coverage | (existing PREP) | **064 EXECUTING**; 062→066 staged |

### L2 — Code↔canon divergence
| ID | P | Gap | Paths | Depends |
|---|---|---|---|---|
| A-L2-M-CANON | P0 | Canon M-from-Human example vs TW Move + 056 all-printables (hub ruled; Max entry) | `control-and-escalation.md` · `mode-line…` | **CLOSED** ADR-002 fold |
| A-L2-SPECTATE-RV | P2 | Reverse-video vs plain Spectate chip | findings DOC-GAP | Max/hub |
| A-L2-APP-LABEL | P2 | Canon short **App** vs shipped `APP` chip string | `control_seat.py` · mode-line | **Ruled** Batch 2/3 docs-win `APP` |

### L3 — Defined-but-unwired
| ID | P | Gap | Paths | Depends |
|---|---|---|---|---|
| A-L3-ATTACH-READ | P0 | `AttachInputConn` unbounded `readline` | `session/attach_client.py` | none (banked) |
| A-L3-D10-PROOF | P1 | Guardian D10 keepalive present; unsafe-screen suppress Accept not tip-proven as 028 DONE | `session/guardian.py` · inventory | 027 |
| A-L3-GUARDIAN-STOP | P2 | Guardian notes STOP+Human escalate “follow-up” | `guardian.py:166` | 064/065 |
| A-L3-ART-HINTS | P1 | screens comments reserve A/R/T / N5 — unwired | `screens.py` | 066/071 |
| A-L3-SESSION-F6 | P3 | Transcript order before vs after `sendall` | `connection.py` · `session.py` | **BANKED** |
| A-L3-SESSION-F7 | P3 | `daemon_running` over failed status round-trip | `cli.py` | **BANKED** |
| A-L3-SESSION-F8 | P3 | watch frame parse gaps vs `--frames N` | `cli.py` | **BANKED** |
| A-L3-CLASSIFY-AUDIT | P2 | `classify.py` unaudited (except secret-prompt regex) | `session/classify.py` | future audit WO |

### L4 — Cleanup
| ID | P | Gap | Paths | Depends |
|---|---|---|---|---|
| A-L4-LEGACY-WO | P2 | Root `WO-00…17` map to PWO but look like live queue | `workorders/WO-0*.md` · README | docs |
| A-L4-ARCHIVE-CITES | P2 | Many canon cites still archive-only symbols where tip has `cockpit/` | canon surfaces | progressive |

### L5 — Doc-gaps / design-flaws
| ID | P | Gap | Paths | Depends |
|---|---|---|---|---|
| A-L5-CTRL-]APP | P1 | Ctrl-] from App-hold unruled no-op | findings · 061 follow-on | **Ruled** no-op stay App |
| A-L5-ENTRY-PICKER | P2 | Entry consolidated picker still heavily `[ASPIRATIONAL]` | `entry-and-profile-selection.md` | Phase 1+ |
| A-L5-TEACH-OVERLAY | P2 | Teach-overlay cyan indicator ASPIRATIONAL | mode-line · visual-language | 069 |

### L6 — ADR-rollup candidates
| ID | P | Gap | Paths | Depends |
|---|---|---|---|---|
| A-L6-M-DUAL | P1 | Spectate→Human + parked Human→App need signed dual-path ADR when Max picks B′/C | DECISIONS/ADR | **superseded** Batch 1b+2/3 (Ctrl-A; Spectate≠Mode) |
| A-L6-NORTH-STAR | P0 | One-cockpit draft parked — Max (1)(2) | `.samantha/specs/` | **SIGNED** `north-star.md` Batch 2/3 |
| A-L6-NO-AI-DRIVE | P2 | Vocabulary gate + MODE_APP-only lock already ship — fold “no AI live sender” into accepted ADR when 085 closes | control_lock · findings | 085 |

## Priority order (buildable overnight / morning)

1. ~~**WO-AUDIT-HARDEN-ATTACH**~~ (**DONE** `88004d8` · WO tip-stamped)
2. ~~**WO-AUDIT-OKF-052-TIP**~~ (**CLOSED** — ULTRACODE 052 DONE `de47a26`; no false PREP claim)
3. **WO-AUDIT-P025-LEDGER-HONESTY** (P1 · docs+thin PREP; product later)
4. **WO-AUDIT-P028-KEEPALIVE-STATUS** (P1 · tip inventory honesty / proof gap)
5. **WO-AUDIT-LEGACY-WO-INDEX** (P2 · docs)
6. **WO-AUDIT-PHASE6-PREP** (P2 · docs PREP; do not invent product scope)
7. ~~**WO-AUDIT-CTRL-RBRACKET-APP-HOLD**~~ (**Ruled** Batch 2/3 — no-op stay App; CC product pin)
8. ~~**WO-AUDIT-APP-LABEL-CASE**~~ (**Ruled** Batch 2/3 — chip `APP` docs-win)

062–072 remain the product spine after Max Human→App — do not duplicate those WOs here.
