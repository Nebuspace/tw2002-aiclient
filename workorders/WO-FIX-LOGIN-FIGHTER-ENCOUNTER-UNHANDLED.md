# WO-FIX-LOGIN-FIGHTER-ENCOUNTER-UNHANDLED

**Goal:** A fresh registration can land in a hostile starting sector before
`ensure` ever hands control to `sector_explore`'s own automaton — this session's
live-prove run against a real TWGS server hit exactly that gap: `_decide()` in
`login.py` had no branch for the `fighter_encounter` classification, so login
halted unhandled on the very first NPC toll a new character met.

**Scope:**
- `tw2002_aiclient/session/login.py` — new `fighter_encounter` branch in
  `_decide()`; imports `fighter_toll_policy`, `FIGHT_FORBIDDEN_KEYS`,
  `FIGHT_LETTER_ALLOWLIST` from the existing `sector_explore` module
- `tests/test_login_fighter_encounter.py` — new
- this WO file

**Out of scope:**
- Inventing a second combat-decision engine. `classify.py` already classifies
  `fighter_encounter`; `fighter_toll_policy.py` already holds the full
  Max-ratified (`RESOLVED-COMBAT-AUTOFIGHT-90`, 2026-07-28) guarded engine,
  already wired into `sector_explore.py`'s explore-mode automaton. This WO
  only wires the SAME policy into the login/registration path.
- The post-Attack quantity prompt (`How many fighters do you wish to use…`)
  classifies separately as `money_prompt`, which is in
  `NEVER_AUTO_ACTION_CLASSES` — login.py structurally cannot and does not
  auto-answer it. A bounded, intentional residual, not a bug: the operator
  still gets the keyboard for the quantity commit.

**Constraints:**
- Reuse `fighter_toll_policy.next_encounter_input` exactly as
  `sector_explore.py` does — never a second/divergent decision path.
- Independent second layer mirroring `sector_explore.py`'s own
  `_fight_key_permitted`: the returned key is checked against
  `FIGHT_FORBIDDEN_KEYS`/`FIGHT_LETTER_ALLOWLIST` in `login.py` itself, so a
  future edit to the policy's own logic cannot reach the socket without also
  editing here.
- Halt (`decision.halt` or no key) raises `LoginError` with the policy's own
  reason string — never a silent fall-through, never a guess.
- PvP is a hard STOP (inherited from the policy's `pvp_hard_stop`); Pay (`P`)
  is structurally unreachable (`P` is in `FIGHT_FORBIDDEN_KEYS`, not in
  `FIGHT_LETTER_ALLOWLIST`).

**Accept:**
1. A winnable NPC fight (force_share ≥ gate, enemy count within band)
   auto-Attacks.
2. Below the gate or an unwinnable band retreats.
3. A PvP-marked frame raises `LoginError` (`fighter_encounter_halt:pvp_hard_stop:…`).
4. Unparsed counts retreat rather than guessing (matches the policy's own
   `unparsed_counts_retreat` exit — never a halt for this specific case, per
   `decide_encounter`'s `counts_present` branch).
5. `P` is provably unreachable via both the allowlist and forbidden-key sets.

**Proof:** `.venv/bin/python -m pytest tests/test_login_fighter_encounter.py tests/test_login.py tests/test_login_connect_splash.py -n0 -q` → 13 passed.
