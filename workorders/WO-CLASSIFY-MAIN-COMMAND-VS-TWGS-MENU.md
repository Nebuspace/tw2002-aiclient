# WO-CLASSIFY-MAIN-COMMAND-VS-TWGS-MENU

**Status:** OPEN · **P0** — blocks extreme Play prove / ensure truth  
**Posted:** 2026-07-27T05:32:00Z · hub ruling on CC `❓` (Max GO already: prove extreme)  
**Seat:** `impl-aiclient-cursor` (disjoint from mint: `classify.py` + tests/fixtures only)  
**Depends:** tip ≥ `5bb96b7`

## Goal

`classify` / `classify_screen` must **not** return `main_command` for the TWGS door **Main Menu** prompt. That class must mean the **in-game sector** command prompt only.

## Live false-positive (2026-07-27 extreme prove)

On `tw.worldsapart.net:2002`, ensure reported `ok:true · classification=main_command` for:

```
Command [TL=00:00:00]:[Main Menu] :
```

True in-game target looks like:

```
Command [TL=00:00:00]:[54] (?=Help)? :
```

Today’s gate is only `command\s*\[\s*tl\s*=` (`classify.py` ~958) — both match. Downstream Play/explore would drive a **door menu**.

## Scope

- `tw2002_aiclient/session/classify.py` — narrow `main_command` matcher (and/or add an earlier refuse for `[Main Menu]` / non-sector form)
- `tests/test_classify.py` + fixture under `tests/fixtures/` (or existing corpus path)
- Pins:
  1. Prompt `Command [TL=00:00:00]:[Main Menu] :` → **not** `main_command` (prefer `unknown` or honest `menu` if already defined — **do not invent a new screen_class** without hub GO; default **`unknown`**)
  2. In-game `Command [TL=…]:[<int>] (?=Help)? :` → still `main_command`
  3. Stale-scrollback: Main Menu text above a real sector prompt must not poison; real sector prompt above leftover menu chrome must still win (mirror existing stale-scrollback discipline)
  4. **Mutation:** deleting the Main Menu refuse must turn the menu fixture back to `main_command` (prove the pin is load-bearing)

## Constraints

- **No new `screen_class`** without hub GO — land menu on `unknown` (or existing `menu` only if the full screen truly matches that class’s anchors).
- Do not broaden other gates. Cipher/Mack recommended on classify change.
- Disjoint from `WO-PASSWORD-MINT-CANON` paths — can land in parallel PR.

## Accept

1. Menu prompt fixture → not `main_command`; mutation red when refuse removed.
2. Existing `main_command` / computer-wins / stale-scrollback pins stay green.
3. PR + STATUS.

## Proof

`pytest tests/test_classify.py -q` (or targeted) + mutation note in STATUS.

## Follow-on

Re-HANDOFF `WO-PLAY-LIVE-EXTREME-PROVE` after this tip is on main (ensure must reach real sector `main_command`).
