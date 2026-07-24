# WO-P3-030…033 — Trainer-cockpit frame · PREP

> Status: PREP (Phase 3 · authored on Opus 4.8 — **product build-wave is Fable-gated**, no cockpit chrome code until Max/harness switches this seat to Fable)
**Phase:** 3 · **Type:** PREP (inventory + tightened Accept/Proof) · **Seat:** impl-claudecode-aiclient · **Model (execute):** Fable
**Canon:** `canon/surfaces/trainer-cockpit.md` · `canon/surfaces/visual-language.md` · `canon/ADR/001-one-tree-embedded-session.md`
**Refs:** `workorders/ULTRACODE-WO-INVENTORY.md` rows 166-169 · archive `.../twclient/spectate_layout.py` + `spectate_app.py` (port source, reference-only)

Authored from a 3-worker read-only fan-out (cockpit↔canon inventory · Accept/Proof · geometry hazards). **No product edited.**

---

## 0. Strategic framing (absorb before execute)

- **Not materialized:** PWO-030…033 exist only as inventory rows; this PREP authors their Accept/Proof.
- **The live `tw2002_aiclient/screens.py` is a single-`stdscr` launcher — do NOT extend it for the frame.** `PlayShellScreen` (`screens.py:295-358`) is an explicit placeholder (`PLAY_SUBTITLE = "(placeholder — cockpit chrome is a later WO)"`): one single-line `stdscr.box()`, flat metadata rows, `status_line`, Esc footer.
- **Proven geometry lives in the archive and is NOT importable** (`pyproject.toml` packages `tw2002_aiclient*` only; `import twclient` → ModuleNotFoundError). So the execute must **port `frame_layout` + the width constants into a NEW pure geometry function in `tw2002_aiclient`** (e.g. `tw2002_aiclient/cockpit/layout.py::frame_layout(lines, cols) -> regions`). Canon's constants (`VIEWPORT_W/H=82/26`, `PRIORITIES_W=HUD_GUTTER_W=36`, fold floors `154/138/118/82/60`) are the **target contract**, cited as numbers, not live symbols.

## 1. Per-PWO tightened Accept + Proof

### PWO-030 — Play-chrome navigation (VERIFY; likely already satisfied)
- **Live state:** DONE in substance — Esc→`"back"` (`screens.py:354`), clean launcher return (`app.py:151-152`), no transient carried back; `TW2002_HANDOFF_SMOKE` path at `app.py:180-199`.
- **Accept:** Enter on a healthy launcher row → play shell with that profile's handle visible; Esc → clean launcher return (router `"back"`, not process exit); re-entry carries ZERO play-shell transient. **Daemon-survival (ADR-001 app-disposable/daemon-continuity):** Esc must NOT tear down the session — after return, `tw status` still reports the daemon alive/reattachable. **Out of scope (explicit):** the "Stop the daemon too? (Yes/No)" exit-confirm popup — canon assigns it to mode-line N5 (`trainer-cockpit.md:171-180`), Phase 5. 030 asserts only Esc→launcher with daemon survival.
- **Proof:** Layer-B pty (mirror `test_interactive_app.py::_run_attach_in_pty`, 24×80, skip-guard): select+Enter → `_find_text(grid,"<handle>")`; Esc(27) → launcher reappears, play-only text gone; daemon-survival leg against an isolated FakeSession (assert session still live after Esc; never touch `run/twd.sock`).

### PWO-031 — Outer border frame (BUILD)
- **Live state:** MISSING — only single-line `stdscr.box()`; no double-line, no two-weight system.
- **Accept:** One **double-line** outer frame at exactly row 0 / col 0 / `max_y-1` / `max_x-1`, cyan+**bold**. **Two-weight hierarchy:** outer frame + game viewport double-line (`╔═╗║╚╝`); every instrument box thin-rounded (`╭─╮│╰╯`); `TW2002_ASCII=1` (`unicode_ok=False`) degrades both to ASCII twins with no loss of box closure. No region border overlaps another or draws outside the outer frame at ≥80×24; below floor, refuse with `Terminal too small (C×L) — need at least 60×20`.
- **Proof:** Layer-A — the new reborn `frame_layout`: assert corner/edge coords + `mode=="too_small"` below floor (mirror `test_spectate_layout.py:292-330`). Layer-B — pty 40×160: four corner glyphs at the four corners; `screen.buffer[0][0].fg=="cyan"` and `.bold`; an ASCII-twin run; no two region borders share a non-corner cell.

### PWO-032 — Character / profile strip (EXTEND)
- **Live state:** PARTIAL — data present as a vertical list (`screens.py:337-340`), not a top band.
- **Depends-on (verify first):** is `world_identity.world_id_from_profile` ported into `tw2002_aiclient/session/`? (archived today — buildability gate).
- **Accept:** Row 1 (inside the outer frame) renders a character/profile strip `host · game-letter · handle` (with the `·` glyph), not the profile id alone; a broken/unresolved profile shows `?`/`—` for missing fields, no crash/blank; the strip truncates to line-tail at minimal tier, never wraps/h-scrolls.
- **Proof:** Layer-A — unit-test the pure strip-composer (fixture profile + broken profile → exact string + `?`/`—` fallbacks). Layer-B — pty: `_find_text` for `<host>`+`<handle>` on row 1; broken-profile run asserts `?`/`—` + no traceback.

### PWO-033 — Three-column body scaffolding (BUILD)
- **Live state:** MISSING entirely.
- **Accept:** Between the row-1 strip and the bottom full-width `[LOGS]` band, three columns: left gutter titled `PRIORITIES`/`GOALS` (w=36), center game slot (w=82 or remainder), right gutter titled `HUD` (w=36) — each thin-rounded titled box, title at `(0,2)` cyan. Empty panels state emptiness honestly (`—`/`(none yet)`), never vanish. **Fold ladder** (body never h-scrolls, gutters shed first, center survives last): full≥154 · wide-right≥138 (left gutter narrows to `PRIORITIES_MIN_W`=20) · narrow-right≥118 (left gutter dropped) · minimal≥82 (bordered viewport alone) · no_border≥60 · too_small<60.
- **Proof:** Layer-A (primary) — reborn `frame_layout`: assert `mode` + each column `x/w` at the five tier boundaries (154/138/118/82/60), `center["w"]==82` at full, left-gutter absent below 138 (mirror `test_spectate_layout.py:313-364`). Layer-B — pty 40×160: `PRIORITIES`/`HUD`/`GAME` titles at expected columns; narrow run asserts the fold (left gutter gone, nothing past `max_x-1`).

## 2. The TUI-proof convention (hard constraint — NEVER ANSI-regex)
- **Layer A (pure, no curses):** call the pure `frame_layout`/compose function, assert the returned regions/strings. Models: `tests/test_spectate_layout.py:292,313,364` · `tests/test_aiclient_play_panels.py:41` (`adapters.compose_play_panels`).
- **Layer B (real-curses pty + pyte replay):** `pty.openpty()` + `TIOCSWINSZ` winsize (`test_interactive_app.py::_set_winsize`), drive keystrokes into the master fd, replay raw bytes through `pyte.Screen`/`Stream`. Assert **geometry/text** via `_pyte_grid()`/`_find_text()` (`test_spectate_app.py:376,380`); assert **color/attr** via `cell = screen.buffer[r][c]; cell.fg / .reverse / .bold` (`:604-607`); cursor via `screen.cursor.y/x`. **Isolation:** scripted `FakeClient`/`FakeSession` on a temp socket, never `run/twd.sock`. **Skip-guard:** `pytestmark = pytest.mark.skipif(not pty_curses_supported())`.

## 3. Geometry guard list (bake into 031/033 Accept)
1. Every cell write `addnstr(y, x, text, max(0, w-x-1), attr)` inside `try/except curses.error`; borders via a shared `_draw_box` with per-side try/except — the bottom-right-cell throw is EXPECTED, not a bug.
2. Viewport content = **full 80×24 `raw_display()`** (not `render_cropped()`) at inset (1,1), **clipped not scaled/inset**; zip with `color_map()` by row index (identical bbox).
3. **Fold, never horizontal-scroll:** width-tiered panel shedding; clamp every region ≥1×1 before `newwin`; a failed `newwin` drops that one pane, never the loop.
4. Min-size ladder from the **constants** (not the stale `>=142` docstring): full≥154 · 138 · 118 · 82 · 60 · refuse<60.
5. Persistent per-pane windows rebuilt **only** on `KEY_RESIZE`/tier-change (`update_lines_cols()` first); batch `noutrefresh()` + one `doupdate()`; decouple the ~13fps chrome tick from the event-driven viewport redraw (no per-frame `newwin`/full `erase()` of static chrome).
6. The intervention/STOP strip claims leftover height **first**, ahead of control strip + ticker (safety-legibility invariant).

## 4. Cross-cutting depends-on / decisions for the hub
- **D1 — Test-suite rehab is a hard Depends-on.** The pty proof harnesses (`test_spectate_app.py`, `test_spectate_layout.py`, `test_interactive_app.py`, `test_aiclient_play_panels.py`) import `twclient.*` and don't import at root (`WO-TEST-SUITE-REHAB.md`). Each frame WO must either reuse a rehabbed harness OR ship a `tw2002_aiclient`-targeted pty helper — name which.
- **D2 — Introduce a reborn pure geometry function** (`frame_layout` analogue in `tw2002_aiclient`) so 031/033/039 geometry gets cheap Layer-A tests; without it the "no overlap / fold order" criteria stay soft.
- **D3 — Verify `world_id_from_profile` is ported** before 032 is buildable.
- **D4 (DOCS-WIN, do in the port):** correct the canon-self-flagged stale fold-floor docstring `>=142` → `154` (`visual-language.md:210-214`).
- **D5 (name, don't reintroduce):** archived `_MODE_BADGES` still carries an `ai_pilot→"AI-PILOT"` live-driver slot and a wrong-axis coverage meter (`trainer-cockpit.md:399-401,427-434`) — belong to the mode-line WO; the frame build must NOT reintroduce an AI-drives slot.
- **D6 — Exit-confirm popup scoping:** the ADR-001 "Stop the daemon too? (Yes/No)" popup is canon-assigned to mode-line N5 (Phase 5), OUT of PWO-030. Confirmed here; noted so it doesn't fall through the 030↔N5 seam.

## 5. Execute readiness
PWO-030 = verify-only (buildable now). PWO-031/032/033 = greenfield-port against a placeholder, gated on D1 (harness) + D2 (geometry fn) + D3 (world-identity, 032 only). **All execute is Fable-gated per Max's Phase 3-5 UI carve-out** — this PREP unblocks planning only.
