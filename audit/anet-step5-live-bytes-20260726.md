# a-net step-5 live bytes vs fixture — hub capture 2026-07-26T18:59Z

**Tip under test:** `814d50c` / `origin/main`  
**Bank capture dir:** `/tmp/tw2002-live-ensure-matrix-20260726T0801Z/reprove/anet-step5-capture-185955Z/` (outside git)  
**Files:** `live_step5_screen.txt` · `ensure.json` · `classify_result.txt` · `screen.json`

## Experiment result (decisive)

| Check | Result |
|---|---|
| `ensure` error | `login_failed:automaton_stuck:classification='menu':step=5` |
| `classify_screen(live_bytes)` | **`menu`** |
| Committed fixture classify | `game_select` (prior) |
| Live lines / fixture lines | 23 / 26 |
| Unified diff hunk lines | 52 |

**Verdict:** live step-5 bytes classify as **`menu`**, not `game_select`. The committed fixture is **not representative** of what `ensure` meets at step 5. Fault is **at/before classification of the live paint** (option 1 in WO) — not “downstream of a correct game_select.”

**Next (Cursor):** redacted fixture from live bytes (or bounds fix driven by live layout) + pins; do **not** invent a new `screen_class` without hub GO. Diff live vs fixture for the structural delta (banner/box/option tokens).

No credentials or full frames in this note.
