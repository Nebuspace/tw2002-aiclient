# Live ensure matrix — RETURNING sprint wave `returning-sprint-2312Z`

**Seat:** orchestrator (hub laptop) · **Tip under test:** `origin/main` `9bffbf8`  
**Bank:** `/tmp/tw2002-live-ensure-matrix-20260726T0801Z` (outside git; never commit)  
**Wave dir:** `…/reprove/returning-sprint-2312Z/`  
**Context:** Max sprint GO 2026-07-26T23:12Z — close M2 gaps left as honest unknowns on the confirming wave.

No credentials, handles, or screen dumps in this file. Public hostnames only.

---

## Cells this wave

| Cell | Profile | Letter | Classification | Steps | ok |
|---|---|---|---|---|---|
| micro RETURNING | `proof_micro` | B | `main_command` | 10 | true |
| a-net RETURNING | `proof_anet` | A | `main_command` | 10 | true |
| rogue RETURNING (regression) | `proof_rogue` | A | `main_command` | 9 | true |

**3/3 PASS** on this wave.

---

## Ladder status after this wave (tip `9bffbf8`)

| Milestone | Status |
|---|---|
| **M1** NEW → `main_command` | Met — rogue / micro / a-net NEW (prior confirming wave `confirm-195540Z`) |
| **M2** RETURNING → `main_command` | **Met** — rogue (prior) + micro + a-net (this wave) |
| **M3** game select × hosts | Met on proved hosts · xeno remains honest halt (untaught door) |
| **M4** sector explore | In flight — `WO-EXPLORE-SECTOR-FRONTIER` HANDOFF'd (Explore HOLD lifted) |

**≥3-host ensure bar (NEW and RETURNING):** satisfied for rogue · micro · a-net.

---

## Not this wave

| Cell | Status |
|---|---|
| xeno | N-A — honest halt · Phase-2 Max-gated · fingerprint already on main |

---

## Refs

- Prior confirming NEW wave: `audit/live-ensure-matrix-a5cfdda-20260726.md`
- Sprint plan: `.samantha/plans/ensure-game-explore-sprint-20260726.md`
- Checklist: `audit/hub-live-ensure-reprove-checklist-20260726.md`
