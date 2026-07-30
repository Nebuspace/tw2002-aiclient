# NEVER_AUTO_ACTION consumer audit — 2026-07-26

**WO:** `WO-NEVER-AUTO-ACTION-CONSUMER-AUDIT`  
**Closes:** `audit/session-classify-audit-coverage-20260726.md` C-06  
**Mode:** offline — no live connects  
**Pins:** `tests/test_never_auto_action.py`

---

## Goal (restated)

Every send path that **keys off screen classification to choose a keystroke**
must either:

- **(a)** intersect `classify.NEVER_AUTO_ACTION_CLASSES` / refuse `money_prompt`, or
- **(b)** fail-closed via a `main_command`-only whitelist (money cannot match).

Classification that is **reported** but does not decide what to press is out of
scope (status / read / history / HUD chips).

---

## Inventory — classification → send consumers

| # | Module · site | How it chooses a keystroke | Refuse shape | Pin(s) |
|---|---|---|---|---|
| 1 | `menu/crawler.py` · `screen_state` | Enumerate / press only when screen is "safe" | **(a)** `_NON_MENU_GATE_CLASSES` unions `NEVER_AUTO_ACTION_CLASSES` → `"unsafe"` | `test_the_crawler_refuses_to_enumerate_a_money_prompt` · `tests/test_menu_crawler.py` class-alone pins |
| 2 | `loops/player.py` · `_gate` (taught-macro / arm fire) | Halt before every send at every boundary | **(a)** `observation.klass in NEVER_AUTO_ACTION_CLASSES` → `HALT_NEVER_AUTO_ACTION` | `test_the_taught_loop_player_refuses_a_money_prompt` · `tests/test_loop_player.py` mid-loop / recorded-answer pins |
| 3 | `session/guardian.py` · `_maybe_keepalive` | Idle blank Enter | **(b)** `cls != "main_command"` → return (no send) | `test_the_guardian_never_nudges_a_money_prompt` |
| 4 | `session/daemon.py` · `_attempt_graceful_quit` | Best-effort `Q` / `Y` on shutdown | **(b)** `session.classify() != "main_command"` → return | `test_graceful_quit_never_keys_a_money_prompt` |
| 5 | `session/login.py` · `_decide` | Login automaton positive table | **(b)** unrecognized class (incl. `money_prompt`) → `None` (no keystroke) | `test_the_login_automaton_has_no_keystroke_for_a_money_prompt` · `test_no_consumer_acts_on_merely_being_recognized` |
| 6 | `session/protocol.py` · `_dispatch_ensure` | "Already there?" before login replay | **(b)** `cls == target` with default `target="main_command"` | `test_ensure_never_treats_a_money_prompt_as_a_reached_target` |
| 7 | `session/sector_explore.py` · `_gate_screen` | ExploreRunner warp hops from `main_command` only | **(a)** `klass in NEVER_AUTO_ACTION_CLASSES` → `HALT_NEVER_AUTO_ACTION` | `test_inventoried_consumers_still_carry_their_refuse_marker` · structural inventory pin (#7 additive — see below) |
| 8 | `session/hud_seed.py` · `seed_hud_after_join` | One read-only `I` ship-info probe | **(b)** `session.classify() != "main_command"` → return (no send) | `tests/test_hud_complete_producers.py` unsafe-screen pin · structural inventory pin |

### Taught-rule / cockpit arm (C-06 residual)

- **Fire path:** cockpit ARM is presentation-only (`cockpit/arm.py` — no
  `classify`, no send). Arming a taught run goes
  `protocol.autoloop_start` → `session/autoloop.py` → `loops/player.py`.
  The **only** classification→send decision for taught macros is consumer **#2**.
- **`session/autoloop._ReplayPort`:** deliberately does **not** re-classify or
  refuse; the player owns every safety gate (documented in-module). Not a
  separate consumer.

### Not consumers (classify present, no classification-chosen send)

| Surface | Why excluded |
|---|---|
| `session/protocol.py` `do` / `send` | Operator-supplied keystrokes; classify is reported, not consulted for *what* to press |
| `session/protocol.py` `status` / `read` / `state` / `screen` | Read-only reporting |
| `loops/recorder.py` | Derives `expected_post_class` at capture; does not send from class |
| `cockpit/arm.py` / HUD chips | Read daemon status; no wire send |
| Human `attach` / `send_raw` | Human sender; not App auto-action |

---

## Regression tripwire

`tests/test_never_auto_action.py::test_inventoried_consumers_still_carry_their_refuse_marker`
asserts each inventoried source file still contains its refuse marker.
Dropping the union / whitelist / positive-table shape fails that pin before
behavior can silently widen.

`test_no_uninventoried_classify_send_module` fails if a new package module both
references `classify_screen` / `.classify(` and an App send symbol without
appearing in the inventory frozenset — the "fifth consumer" trap C-06 named.

---

## Additive corrections

Row **#7** (`session/sector_explore.py` · ExploreRunner) was omitted from the
original six-consumer verdict when Explore was still HOLD. The refuse shape was
already present in product code (`klass in NEVER_AUTO_ACTION_CLASSES` in
`_gate_screen`); this entry **extends** the inventory without rewriting rows
1–6 or retracting the prior refuse analysis for those sites.

Row **#8** adds the cold-join HUD ship-info probe. It sends only from a
positive `main_command` classification; fighter dialogues, money prompts,
unknown screens, human-held sessions, and spectate paths therefore cannot
reach the send.

---

## Verdict

C-06 **CLOSED** for this tip (rows 1–8): every classification→send consumer is
inventoried, refuse-shaped, and pinned. No product classify vocab change; no
live connects required for this inventory extension.
