# Live ensure matrix — multi-host re-prove (redacted skeleton)

**WO:** `WO-ENSURE-MULTIHOST-REPROVE` · **Seat:** `impl-aiclient-cursor` (prep) · **Hub:** laptop live cells  
**Sprint:** M1–M3 Accept · step **[4]** · **PR:** #20 · branch `wo/ENSURE-MULTIHOST-REPROVE`  
**Prove tip (product under test):** `origin/main` `7e43af6` (killpg honesty) — re-prove on that tip or later FF of main  
**Prep tip (this PR):** seed `4412046` + this artifact  
**Isolated config:** `/tmp/tw2002-live-ensure-matrix-20260726T0801Z` (chmod 700 · outside tree · never commit)  
**Isolated run-dir:** required whenever `TW_CONFIG_DIR` is set (fail-closed without `--run-dir` / `TW_RUN_DIR`)

No credentials, handles, FQDNs beyond public game hosts, or screen dumps in this file.

---

## Host order (hub-decided — DEC-09 · no Max idle)

| # | Host | Profile key (bank) | Letter (prior matrix) | Expectation @ tip `7e43af6` |
|---|---|---|---|---|
| 1 | `roguetw.net:2002` | `proof_rogue` / `proof_rogue_new` | A | **PASS** NEW and/or RETURNING → `main_command` (regression) |
| 2 | `game.a-net-online.lol:2002` | `proof_anet` | C | Banner/`game_select` + letter → `main_command` (NEW and/or RETURNING) |
| 3 | `twgs.microblaster.net:2002` | `proof_micro` | B | Run **after** `WO-MICRO-LOGIN-BLANK-REJECT` merges; until then honest **FAIL** / **SKIP** OK — **do not block** hosts 1–2 |
| 4 | xeno / `twgs.exiled.org:2002` | capture-only / prior bank | — | **Halt without invent** — Phase-2 `[A]` shape banked; cell = honest FAIL / N-A unless prior capture already suffices |

---

## Results matrix (fill on hub live)

| Server | Letter | NEW | RETURNING | Error class / notes | Live-proved by |
|---|---|---|---|---|---|
| `roguetw.net:2002` | A | **PASS** (`main_command`) | **PASS** (`main_command`) | Tip `7e43af6` · isolated run-dirs under bank `reprove/` · regression clean | hub 18:53–18:55Z |
| `game.a-net-online.lol:2002` | C | **FAIL** (`menu`@step5) | **FAIL** (`menu`@step5) | Same class as prior wave despite `WO-ANET-BANNER-LAYOUT` + letter on main — `login_failed:automaton_stuck:classification='menu':step=5`. **Not inventing**; bank follow-on diagnosis WO. | hub 18:55Z |
| `twgs.microblaster.net:2002` | B | **DEFER** until blank-reject on main | **SKIP** | CC `WO-MICRO-LOGIN-BLANK-REJECT` still open | hub (post-merge) |
| xeno / exiled | — | **N-A / honest halt** | **N-A** | Phase-1 fingerprint stands; no invent this wave | prior capture |

**Accept bar:** ≥3 hosts **attempted**; each cell NEW and/or RETURNING with outcome + error class; PASS cites `main_command` under isolated run-dir; FAIL is honest (blank-reject residual · untaught door · remote stall) — no invent.

---

## Evidence paths (local `/tmp` only — hub fills)

Use a **fresh isolated run-dir per cell** under the bank (or a dated sibling). Suggested names:

| Cell | Suggested JSON / log |
|---|---|
| rogue NEW | `…/reprove/ensure-rogue-new.json` |
| rogue RETURNING | `…/reprove/ensure-rogue-returning.json` |
| a-net NEW | `…/reprove/ensure-anet-new.json` |
| a-net RETURNING | `…/reprove/ensure-anet-returning.json` |
| micro NEW | `…/reprove/ensure-micro-new.json` (post blank-reject) |
| xeno halt | cite `/tmp/xeno-capture-20260726/` and/or `audit/xeno-fingerprint-20260726.md` — do not invent class |

---

## Prior wave (closed — do not treat as this tip's Accept)

See `audit/live-ensure-matrix-20260726.md` — tip base ≥ `ca8108a` / `50bbc46`; rogue PASS; micro FAIL `unknown`@6; a-net FAIL `menu`@5. Follow-ons since: ANET banner layout · micro corpus → blank-reject · xeno Phase-1 fingerprint · letter autoselect product.

---

## Cursor prep vs hub live

| Layer | Owner | Status |
|---|---|---|
| Redacted skeleton + host order + checklist | Cursor (this tip) | **DONE** (prep) |
| Live ensure cells on laptop | Hub | **PENDING** |
| `live-prove` Check Run on PR #20 | Hub | **PENDING** after live |
| `session/login.py` blank-reject | CC | **IN FLIGHT** — stay off |
| Xeno Phase-2 invent | — | **OUT** (Max/catalog) |

---

## Hub close (fill later)

- Tip SHA live-proved: ________  
- N-of-M: ________  
- Cells deferred: ________  
- live-prove posted: ________  


---

## Hub live wave 2026-07-26T18:53Z (tip `7e43af6`)

| Cell | Result |
|---|---|
| rogue RETURNING `proof_rogue` | PASS `main_command` |
| rogue NEW `proof_rogue_new` | PASS `main_command` |
| a-net NEW `proof_anet` | FAIL `menu`@step5 |
| a-net RETURNING `proof_anet` | FAIL `menu`@step5 (same stuck class) |
| micro | DEFER (blank-reject) |
| xeno | N-A honest halt |

**≥3 hosts attempted:** rogue · a-net · micro(deferred)/xeno(N-A) — Accept bar for *attempt* met; **M1–M3 on a-net not yet green**. Follow-on: diagnose a-net `menu`@5 on tip with banner+letter present (capture before classify invent).
