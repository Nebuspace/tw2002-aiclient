# WO-XENO-GAME-SELECT

**Status:** DONE · CC · classify teach + fixture + pins (live ensure = hub, no bank on this seat)  
**Posted:** 2026-07-27 · Max: cannot pass Exiled game selection — Phase-2 teach GO  
**Seat:** impl-claudecode-aiclient (Fable — classify correctness)  
**Depends:** `WO-XENO-FINGERPRINT` DONE (`f5bfc50`) · live capture `/tmp/xeno-capture-20260726/`

## Goal

`tw ensure --profile xeno` (Exiled / `twgs.exiled.org`) must classify the server’s **square-bracket game-select** door as existing `game_select` and send `profile.game_letter` (already `"B"`) so login reaches `main_command` — same ladder as micro/a-net/rogue.

**Not a new `screen_class`.** Teach a fourth shape of the existing `game_select` class.

## Why Max is blocked

Fingerprint Phase-1 named the door; Phase-2 was left Max-gated as “honest halt.” Classifier returns `unknown` → `_decide` returns `None` → `LoginStalled(automaton_stuck, unknown, step≈6)`. Letter path in `login.py` is already correct once classification is `game_select`.

Live prompt (capture):  
`[ Exiled TW2002 ]:[A][B][C][D][E][X][Z][#]:Timed out...`  
Game rows use **`[A]` square brackets**, not `(A)` / `<A>`. No “Select a game”, no TWGS banner trio, no `Selection (? for menu):`.

## Scope

- `tw2002_aiclient/session/classify.py` — detector + wire into `classify()` and `classify_screen()`
- `tests/fixtures/game_select_menu_exiled_square_bracket.txt` — redacted live capture
- `tests/test_classify.py` — positive + stale-scrollback negative (≥1)

## Out of scope

- New `screen_class` invent
- `login.py` / profile config (already send letter on `game_select`; `[xeno]` already has `game_letter = "B"`)
- Autopilot `game_select` hazard (unchanged — this is **ensure** path)
- IAC / P5-065 / explore

## Detector contract (both signals required)

1. Prompt contains colon-prefixed timed-out: `:\s*Timed\s+out\b` (suffix of custom chrome — **not** `^Timed\s+out`)
2. Body above prompt has ≥2 square-bracket game entries: `^\s+\[[A-Za-z0-9]\]\s+\S+` (multiline)

Either alone is too generic — both required. Name the helper for the shape (Exiled / square-bracket), not a host hardcode in `_decide`.

## Accept

1. Fixture from live capture → `classify_screen` / `classify` → **`game_select`**
2. Stale Exiled rows + unrelated live prompt (e.g. `Command [TL=…]`) → **not** `game_select`
3. Existing game_select fixtures (anet boxed, banner, plain timed-out) still green — no collision
4. Live (hub or seat with Max’s bank): `tw ensure --profile xeno` → `ok:true` · `classification=main_command` (or STATUS with honest failure + capture if host down)
5. Mutation: disable the new detector → Exiled fixture returns `unknown` again

## Proof

```text
pytest tests/test_classify.py -q -n0   # include new cases
# live:
TW_CONFIG_DIR=<Max bank or ephemeral with xeno> \
  ./tw ensure --profile xeno --run-dir <isolated> --json
```

## Refs

- `audit/xeno-fingerprint-20260726.md`
- `workorders/WO-XENO-FINGERPRINT.md` (Phase-2 was gated — **this WO is the Phase-2 execute**)
- Capture: `/tmp/xeno-capture-20260726/settle.json` (`classification=unknown` today)
