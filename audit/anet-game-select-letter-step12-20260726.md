# a-net `game_select`@step12 — letter latch (WO-ANET-GAME-SELECT-LETTER-STEP12)

**WO:** `WO-ANET-GAME-SELECT-LETTER-STEP12` · **PR:** #23  
**Depends:** `main` `25ac393` (chrome-footer `game_select`)  
**Seat:** `impl-aiclient-cursor`

No credentials in this file.

## Symptom

Hub post-#22 ensure (`…/anet-new-postfix-190343Z/ensure.json`):
`login_failed:automaton_stuck:classification='game_select':step=12`
(`screen_withheld=login_failure`). Classify progressed (`menu`@5 → `game_select`);
ensure still dies on the door.

## Hypothesis (primary)

`run_login` latched `game_select_answered` on **any** non-`game_select` class after
`game_select_letter_sent`. A mid-paint flash (`unknown` / generic `menu`) after the
letter send can latch; the door reappears; `_decide` returns `None`; stagnation →
`automaton_stuck` at `game_select`.

Matches design intent of “not on send-confirm alone” but left a hole for false leaves.

## Fix

Latch `game_select_answered` only on **known post-door progress**
(`login_name` / `login_password` / `ansi_prompt` / `char_create` / `pause_key` /
`main_command` / `money_prompt` / module-entry `menu` with `T - Play Trade Wars`).

Pins: `test_game_select_answered_latch_ignores_unknown_flash` + existing
`test_no_double_answer_after_stale_game_select_redraw` (still requires real leave).

## Open / hub live-prove

- Prefer a-net NEW+RETURNING → past door (ideally `main_command`).
- If still stuck: capture `tw screen` + history at fail (letter actually on wire?).
- Alternate residual: host needs Enter on chrome-footer door — bank only with capture.

## Out

invent class · blank-reject · README · xeno Phase-2
