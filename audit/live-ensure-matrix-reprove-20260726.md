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
| `roguetw.net:2002` | A | **PENDING** | **PENDING** | Prior: both PASS @ `main_command` (matrix 09:38Z) | hub |
| `game.a-net-online.lol:2002` | C | **PENDING** | **PENDING** | Prior durable NEW FAIL `menu`@step5 (pre-banner fix); tip has `WO-ANET-BANNER-LAYOUT` — **NEW path not yet live-reproved** | hub |
| `twgs.microblaster.net:2002` | B | **DEFER** until blank-reject on main · else honest FAIL/SKIP | **SKIP** if no persist | Prior: `unknown`@step6 blank-name reject → silence; product fix = CC `login.py` | hub (post-merge) |
| xeno / exiled | — | **N-A / honest halt** | **N-A** | Phase-1 fingerprint: square-bracket door → `unknown`@step6; **no invent** | hub or prior capture cite |

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
