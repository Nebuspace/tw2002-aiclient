# WO-FIX-LOGIN-ANSI-SPLASH-UNHANDLED

**Goal:** Classify sursum_corda-style connect splash ("Please press A B or C
to play after connect") and answer with A/B/C (game *copy* pick — not TWGS
door letter), ending `automaton_stuck:unknown` at step 6.

**Scope:** `classify.py` pre-pass `connect_splash`; `login.py` handler;
tests + this WO.

**Policy:** send `profile.game_letter` when it is A/B/C; otherwise `A`.

## Accept

1. Captured splash text classifies `connect_splash`.
2. Login automaton sends A/B/C and does not stuck on unknown for this screen.
3. Unit pins against live transcript wording.

## Refs

queue-aiclient.md · live `scout_sursum` / `session-20260807T230511Z.log`
