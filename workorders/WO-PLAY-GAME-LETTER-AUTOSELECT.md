# WO-PLAY-GAME-LETTER-AUTOSELECT

**Status:** **HOLD** · Max pace-down (local app restart) · do **not** dispatch until hub lifts HOLD  
**Posted:** 2026-07-26 · Max live report (Manual + timed-out game board; profile `game_letter` never sent)  
**Seat (when lifted):** prefer Claude Code for login/ensure path · Cursor for chrome-adjacent honesty only if lanes split  
**Related (do not merge):** `WO-ANET-BANNER-LAYOUT` · `WO-MICRO-LOGIN-BLANK-REJECT` · `WO-XENO-FINGERPRINT` · ensure bar 1/4 · `autopilot_game_select` halt (canon — **different** from ensure)

## Goal

When the operator's profile has a programmed game letter (e.g. **B**), **ensure / login automaton / App path** must send that letter on a true `game_select` screen so the session enters the chosen game before the host times out — without inventing a screen class, and without weakening Autopilot's **refuse to auto-answer game-select** hazard halt.

## Max's live symptom (operator report)

- Chrome shows **Manual / You have control**.
- Viewport shows an ANSI game-select / menu board **and** a host **"timed out"** (took too long to pick a game).
- App **never** auto-selected the profile's programmed **B**.
- After timeout, reconnect affordance is missing (see sibling `WO-PLAY-CONN-TOGGLE`) — this WO owns the **auto-select / ensure** half only.

## Why this is not "just press B as human"

Canon already treats Autopilot `autopilot_game_select` as a **hazard** — human owns that choice once Autopilot is driving (`canon/architecture/control-and-escalation.md`). That must stay.

Ensure / `run_login` is the opposite contract: `login.py` already maps `game_select` → `profile.game_letter` (single key, no CRLF). If the operator lands on Manual with a live game board and the letter was never sent, something in the chain failed:

1. screen never classified as `game_select` (mislabel `menu` / `unknown` / timed-out prompt shape), **or**
2. ensure stopped / handed Manual **before** the game_select step, **or**
3. `game_select_answered` / letter-sent flags blocked a retry while the host was still waiting, **or**
4. host painted timed-out while still showing a selectable board and we treated it as terminal.

**Diagnose first** with a redacted settled-frame + classification + ensure step — same honesty bar as the live-ensure stalls (no invent class).

## Constraints

- **No invent `screen_class`** without a second Max GO.
- Do **not** teach Autopilot to auto-pick games — only ensure/login / explicit App-ensure path.
- Do **not** weaken stop-on-unknown.
- Timed-out prompt must not falsely drop a still-selectable `game_select` (see existing pin `test_banner_game_select_with_timed_out_as_current_prompt_stays_game_select`) — extend only with live evidence.
- Prefer bounded retry / honest specific failure over hanging.
- Stay off daemon/`./tw` while Max HOLD is active; prove after HOLD lift with isolated `--run-dir` + `TW_CONFIG_DIR`.

## Accept

1. With a profile whose `game_letter` is **B**, isolated ensure on a host that reaches real `game_select` sends **B** and progresses past game-select (or fails with an honest, specific reason — not silent Manual + host timeout).
2. Autopilot still halts on `game_select` / `autopilot_game_select` — pin proves no regression.
3. If classification was the gap: fixture from live redacted capture + adversarial refuse cases still refuse forged/stale boards.
4. Report honest N-of-M if a host cannot be fixed without inventing a class.

## Proof

```text
# after HOLD lift — isolated
pytest tests/test_login.py tests/test_classify.py -k 'game_select' -n0
# live: ensure with profile game_letter=B → past game_select or honest fail
# Autopilot pin: game_select still hazard-halts
```

## Refs

- `tw2002_aiclient/session/login.py` (`game_select` → `profile.game_letter`)
- `tw2002_aiclient/session/session.py` (`game_select_answered` / `game_select_letter_sent`)
- `tw2002_aiclient/session/classify.py` (game_select variants)
- `canon/architecture/control-and-escalation.md` (`autopilot_game_select`)
- Sibling: `WO-PLAY-CONN-TOGGLE.md`
