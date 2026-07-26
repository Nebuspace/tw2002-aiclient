# a-net step-5 live bytes vs fixture — hub capture 2026-07-26T18:59Z

**Tip under test:** `814d50c` / `origin/main`  
**Bank capture dir:** `/tmp/tw2002-live-ensure-matrix-20260726T0801Z/reprove/anet-step5-capture-185955Z/` (outside git)  
**Files:** `live_step5_screen.txt` · `ensure.json` · `classify_result.txt` · `screen.json`  
**Seat follow-on:** Cursor classify/fixture fix on PR #22

## Experiment result (decisive)

| Check | Result |
|---|---|
| `ensure` error | `login_failed:automaton_stuck:classification='menu':step=5` |
| `classify_screen(live_bytes)` @ capture tip | **`menu`** |
| Prior committed fixture (with Selection) | `game_select` |
| Live lines / that fixture lines | 23 / 26 |
| Unified diff hunk lines | 52 |

**Verdict:** live step-5 bytes classify as **`menu`**, not `game_select`. The Selection-ending fixture is **not representative**. Fault is **classification of the live paint** — not “downstream of a correct game_select.”

## Structural delta (live vs Selection fixture)

| Signal | Live capture | Old fixture |
|---|---|---|
| TWGS version + registered | yes | yes |
| Art-embedded `Trade Wars 2002 Game Server` | yes | simplified box |
| `<#>` / `<!>` options | yes | yes |
| `Selection (? for menu):` | **absent** | **last line** |
| Last / prompt line | box-drawing **chrome** | Selection |

Banner/boxed detectors required Selection → live fell through to `menu`.

## Product fix (this tip — no invent)

- Carve-out in `_is_twgs_server_banner_game_select_menu`: when Selection is **absent from the entire grid** and the prompt is TWGS chrome footer, still accept banner + `#`/`!` body (same exclusivity guards).
- Live-derived fixture: `tests/fixtures/game_select_menu_banner_anet_live_chrome.txt` (sanitized).
- Pins: live chrome → `game_select`; adversarial textual non-Selection prompt stays `menu`.
- Old Selection-ending fixture kept green.

**Explicit non-claim until hub live-prove:** ensure NEW/RETURNING → `main_command` on a-net after this tip.

No credentials or full unsanitized frames in this note.
