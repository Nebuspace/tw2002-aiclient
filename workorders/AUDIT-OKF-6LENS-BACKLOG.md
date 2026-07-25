# AICLIENT OKF 6-lens audit backlog

> Seat: `impl-aiclient-cursor` · Tip: `59c4455` (audit drafts) atop `458d140` / product `d4a8829` · UTC: 2026-07-25T05:12Z  
> HANDOFF: `AUDIT-OKF-6LENS` · **No product `.py` in this ticket**  
> HOLDs honored: F2 · G2–G4 · north-star · Human→App (Max B′/C) · auth/secrets  
> Scout cross-check: inventory tip-map confirms 062–072 MISSING; 061/065 PARTIAL; 080 PARTIAL (`classify` LIVE, `state_parser` absent); **085/086 LIVE** (gated); HARDEN-ATTACH still open. Dedup HARDEN vs CC POLISH-SAFE in-flight.

Committable twin: `workorders/AUDIT-OKF-6LENS-BACKLOG.md`. Draft WOs: `workorders/WO-AUDIT-*.md` (8).

## Already queued (dedup — do not re-WO)

| Bucket | IDs | Notes |
|---|---|---|
| Phase-5 PREP | PWO-062…072 | `WO-P5-060-072-mode-teach-PREP.md` — MISSING on tip |
| Pending DOC-GAPs | M-FROM-SPECTATE · POST-DETACH-COPY · SPECTATE-REVERSE-VS-PLAIN · CTRL-RBRACKET-FROM-APP-HOLD | `canon/findings.md` unsigned |
| Banked harden | HARDEN-ATTACH-SOCKET-TIMEOUT | Finding row; drafted as WO-AUDIT-HARDEN-ATTACH · **CC may own overnight** |
| Max-parked | 061 Accept #2 Human→App | B′ vs C — no key invented overnight |
| Phase 6 tip | PWO-080 PARTIAL · 085/086 LIVE · 081–084/087–088 MISSING | Fold into WO-AUDIT-PHASE6-PREP |
| Orphan archive tests | `tests/test_spectate_app.py` etc. still `import twclient` + AI-PILOT expects | cleanup candidate (not product UI) |

## Findings by lens (net-new / honesty)

### L1 — Features in canon/PREP not built
| ID | P | Gap | Paths | Depends |
|---|---|---|---|---|
| A-L1-052-TIP | P1 | ULTRACODE still says PWO-052 PREP while viewport PREP file stamps DONE | `ULTRACODE-WO-INVENTORY.md` | docs-only |
| A-L1-025-LEDGER | P1 | PWO-025 Accept needs ledger actor tags; daemon still “LedgerWriter deferred” | `session/daemon.py` · future `ledger.py` | 041 partial |
| A-L1-P6-PREP | P2 | Phase 6–9 lack tip-honest PREP like Phase 5 | `workorders/WO-P6-*-PREP.md` (new) | after 061 entry |
| A-L1-062-072 | — | Arm/STOP/A·R·T/N5/coverage | (existing PREP) | 060/061 |

### L2 — Code↔canon divergence
| ID | P | Gap | Paths | Depends |
|---|---|---|---|---|
| A-L2-M-CANON | P0 | Canon M-from-Human example vs TW Move + 056 all-printables (hub ruled; Max entry) | `control-and-escalation.md` · `mode-line…` | Max |
| A-L2-SPECTATE-RV | P2 | Reverse-video vs plain Spectate chip | findings DOC-GAP | Max/hub |
| A-L2-APP-LABEL | P2 | Canon short **App** vs shipped `APP` chip string | `control_seat.py` · mode-line | optional polish |

### L3 — Defined-but-unwired
| ID | P | Gap | Paths | Depends |
|---|---|---|---|---|
| A-L3-ATTACH-READ | P0 | `AttachInputConn` unbounded `readline` | `session/attach_client.py` | none (banked) |
| A-L3-D10-PROOF | P1 | Guardian D10 keepalive present; unsafe-screen suppress Accept not tip-proven as 028 DONE | `session/guardian.py` · inventory | 027 |
| A-L3-GUARDIAN-STOP | P2 | Guardian notes STOP+Human escalate “follow-up” | `guardian.py:166` | 064/065 |
| A-L3-ART-HINTS | P1 | screens comments reserve A/R/T / N5 — unwired | `screens.py` | 066/071 |

### L4 — Cleanup
| ID | P | Gap | Paths | Depends |
|---|---|---|---|---|
| A-L4-LEGACY-WO | P2 | Root `WO-00…17` map to PWO but look like live queue | `workorders/WO-0*.md` · README | docs |
| A-L4-ARCHIVE-CITES | P2 | Many canon cites still archive-only symbols where tip has `cockpit/` | canon surfaces | progressive |

### L5 — Doc-gaps / design-flaws
| ID | P | Gap | Paths | Depends |
|---|---|---|---|---|
| A-L5-CTRL-]APP | P1 | Ctrl-] from App-hold unruled no-op | findings · 061 follow-on | Max/hub |
| A-L5-ENTRY-PICKER | P2 | Entry consolidated picker still heavily `[ASPIRATIONAL]` | `entry-and-profile-selection.md` | Phase 1+ |
| A-L5-TEACH-OVERLAY | P2 | Teach-overlay cyan indicator ASPIRATIONAL | mode-line · visual-language | 069 |

### L6 — ADR-rollup candidates
| ID | P | Gap | Paths | Depends |
|---|---|---|---|---|
| A-L6-M-DUAL | P1 | Spectate→Human + parked Human→App need signed dual-path ADR when Max picks B′/C | DECISIONS/ADR | Max |
| A-L6-NORTH-STAR | P0 | One-cockpit draft parked — Max (1)(2) | `.samantha/specs/` | Max |
| A-L6-NO-AI-DRIVE | P2 | Vocabulary gate + MODE_APP-only lock already ship — fold “no AI live sender” into accepted ADR when 085 closes | control_lock · findings | 085 |

## Priority order (buildable overnight / morning)

1. **WO-AUDIT-HARDEN-ATTACH** (P0 · CC may already be on it per POLISH-SAFE)
2. **WO-AUDIT-OKF-052-TIP** (P1 · docs honesty, Cursor)
3. **WO-AUDIT-P025-LEDGER-HONESTY** (P1 · docs+thin PREP; product later)
4. **WO-AUDIT-P028-KEEPALIVE-STATUS** (P1 · tip inventory honesty / proof gap)
5. **WO-AUDIT-LEGACY-WO-INDEX** (P2 · docs)
6. **WO-AUDIT-PHASE6-PREP** (P2 · docs PREP; do not invent product scope)
7. **WO-AUDIT-CTRL-RBRACKET-APP-HOLD** (P1 · parked until Max; draft only)
8. **WO-AUDIT-APP-LABEL-CASE** (P2 · optional polish after Max)

062–072 remain the product spine after Max Human→App — do not duplicate those WOs here.
