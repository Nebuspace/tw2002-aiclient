# WO-ENSURE-MULTIHOST-REPROVE

**Status:** DONE · hub live RETURNING wave `returning-sprint-2312Z` on tip `9bffbf8` · audit `live-ensure-matrix-returning-sprint-2312Z-20260726.md`
**Posted:** 2026-07-26 · sprint critical path **[4]** after letter + a-net banner DONE  
**Depends:** current `origin/main` tip; micro NEW cell may stay FAIL until `WO-MICRO-LOGIN-BLANK-REJECT` merges — **do not block other hosts on micro**  
**Seat:** Cursor prepares Accept artifact + runner notes; **hub runs live laptop prove** (Lane 3) and posts `live-prove`  
**Prep artifacts:** `audit/live-ensure-matrix-reprove-20260726.md` · `audit/hub-live-ensure-reprove-checklist-20260726.md`

## Goal

Re-prove the ensure bar on current main: **NEW and/or RETURNING → `main_command`** on ≥3 hosts with correct profile `game_letter`, isolated `--run-dir`, honest N-of-M table. This is sprint **M1–M3** Accept — not Autopilot.

## Host order (hub-decided — no Max wait)

| Priority | Host | Expectation after current tip |
|---|---|---|
| 1 | `roguetw.net` | Still PASS NEW+RETURNING (regression check) |
| 2 | `game.a-net-online.lol` | Should reach `game_select` (banner) + letter send → `main_command` |
| 3 | `twgs.microblaster.net` | Run after blank-reject lands; until then honest FAIL/`SKIP` OK |
| 4 | xeno/exiled | **Halt without invent** — Phase-2 `[A]` shape stays banked; cell = honest FAIL/N-A unless prior capture already suffices |

Use ephemeral bank under `/tmp/tw2002-live-ensure-matrix-20260726T0801Z` (or successor). **Do not wait** for durable secret-bank Max work.

## Scope

- `audit/live-ensure-matrix-*.md` update (redacted) for this tip
- Optional: thin `scripts/` or docs checklist for isolated ensure cells (no secrets in git)
- WO stamps / sprint plan pointer

**Out:** invent `screen_class` · expand xeno Phase-2 product · `session/login.py` (CC blank-reject) · Autopilot game_select auto-pick

## Accept

1. Redacted matrix table on tip SHA: ≥3 hosts attempted; each cell NEW and/or RETURNING with outcome + error class.
2. Where PASS: evidence path cites `main_command` (or equivalent) under isolated run-dir.
3. Where FAIL: honest class (blank-reject residual · untaught door · remote stall) — no invent.
4. STATUS cites tip + which cells hub live-proved vs deferred.

## Proof

Hub laptop: isolated `ensure` / matrix cells → redacted audit row → `live-prove` on the PR. Cursor midstream: targeted offline only if adding a script/pin.

## Refs

- `.samantha/plans/ensure-game-explore-sprint-20260726.md` step [4]
- Prior matrix: `audit/live-ensure-matrix-20260726.md`
- `WO-MICRO-LOGIN-BLANK-REJECT` · `WO-ANET-BANNER-LAYOUT` · `WO-PLAY-GAME-LETTER-AUTOSELECT` · `WO-XENO-FINGERPRINT`
