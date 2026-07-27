# LIVE prove — extreme Play ladder (A–E)

**WO:** `WO-PLAY-LIVE-EXTREME-PROVE` · **Seat:** `impl-aiclient-cursor`  
**Tip proved against:** `de6ca30` · **UTC:** 2026-07-27T05:44Z–05:56Z  
**Mode:** LIVE — real public TWGS server (`polarwireless.ca:2002`), real daemon.

---

## Verdict

| Leg | Criterion | Result |
|-----|-----------|--------|
| A | NEW char reaches `main_command` via product mint | ✅ PASS |
| B | Second ensure RETURNING (same secrets) → `main_command` | ✅ PASS |
| C | Play shows offer mid-strip with live `log_tail` (observed) | ✅ PASS |
| D | E→y arms explore; hint band shows live progress | ✅ PASS |
| E | Audit committed + PR | ✅ PASS |

**Full Accept. All legs green.**

---

## Environment

```
TW_CONFIG_DIR=/tmp/play-extreme-20260727T0544Z    (secrets.json chmod 600, started {})
TW_RUN_DIR   =/tmp/play-extreme-run-20260727T0544Z
```

Server: `polarwireless.ca:2002` (servers.toml key `polarwireless`), port 2002.  
Profile `extreme_polar`: `allow_register = true`, game letter `A`.  
Fresh handle generated per-run. Sacrificial ship/planet names derived from handle.  
**The minted password was written only to the chmod-600 `secrets.json` in the isolated config — never echoed, never in argv, never in this audit, never in coord.** Password length: len==8 alnum (canonical `generate_password` default; WO-PASSWORD-MINT-CANON).

---

## Leg A — NEW ensure

```
./tw ensure --profile extreme_polar --run-dir "$RUN" --json
```

**Duration:** ~15s  
**Result:** `{"ok": true, ..., "classification": "main_command", "steps": 16, "already_there": false}`

Screen evidence (key lines):
```
Blasting off from <handle>World
Sector  : 52 in Andromeda.
Command [TL=00:00:00]:[52] (?=Help)? :
```

- Sector slot is `[52]` (integer) — **not** `[Main Menu]` → `de6ca30` classify fix confirmed correct.
- Planet `<handle>World` proves our character is new and registered.
- `classification: main_command` — product reached in-game prompt, not TWGS outer door.

---

## Leg B — RETURNING ensure

`./tw stop` issued; then:
```
./tw ensure --profile extreme_polar --run-dir "$RUN" --json
```

**Duration:** ~9s  
**Result:** `{"ok": true, ..., "classification": "main_command", "steps": 9, "already_there": false}`

Screen evidence (key lines):
```
You have been on today.
No messages received.
Sector  : 52 in Andromeda.
Command [TL=00:00:00]:[52] (?=Help)? :
```

"You have been on today." — TWGS's own confirmation this is a RETURNING login.  
`classification: main_command` — product-minted password survived disconnect+reconnect.  
`log_tail` post-B: `["app> ", "app> A", "app> <handle>", "app> Y", "app> T", "app> N", "<<secret input redacted>>", "app> ", "app> "]`  
— redaction sink working; password send masked.

---

## Leg C — Play mid-strip offer visible with live log_tail

Launched `./tw2002-aiclient` in tmux (132×40 window), selected `extreme_polar` via Enter.  
Daemon was connected, `has_real_tail = True` (log_tail non-empty from Leg B session).

Control strip (bottom row) after Play shell loaded:
```
APP  ARM OFF  CONN  session ready — main_command  ·  explore ×5 available — press E
     A)nalyze  R)ecord  T)rigger ○ ⠋ → -
```

This proves `WO-PLAY-OFFER-VISIBLE-ON-LIVE` fix is live:
- LOGS band shows `app>` (real tail → `has_real_tail = True`)
- Offer text is on the mid-strip control segment (not in LOGS fallback)
- Operator can see the offer even with an active daemon transcript

Prior failure mode (tip `9795263`): offer was invisible on live sessions — LOGS had real tail, `status_line` fallback never drew. Now surfaced on mid segment per the fix.

---

## Leg D — E→y arms explore; hint band shows live progress

Pressed `e` in the Play shell.

Control strip after E keypress:
```
Explore x5 LIVE?  y/Nession ready — main_command  ·  explore ×5 available — press E
     A)nalyze  R)ecord  T)rigger ● ⠋ → -
```

ARM gate raised. Pressed `y`.

Control strip immediately after `y`:
```
APP  ARM ON  CONN  explore 0/5…                                explore 0/5… ● ⠋ → -
```

`ARM ON` confirmed. Explore running. Game viewport showed live sector warping:
- Sector 52 → 12 (Aurelia) → 30 (Aurelia) → 1 (The Federation / FedSpace) → 2 (The Federation)

Control strip after completion (~8s):
```
APP  ARM OFF  CONN  explore completed (5)         A)nalyze  R)ecord  T)rigger ○ ⠋ → -
```

`ARM OFF`, `explore completed (5)` — 5 distinct sectors explored. Offer spent. Teach band (A/R/T) returned.

---

## Cleanup

`Esc` from Play shell → profile picker → `q` to exit. `./tw stop` issued.  
tmux session killed. Registered character is sacrificial and abandoned in place.

---

## de6ca30 classify fix proof

Both Legs A and B returned sector prompts with integer sector slots (`[52]`), never `[Main Menu]`.  
The prior failure mode (`[Main Menu]` door prompt matching `main_command`) was NOT triggered.  
`test_twgs_door_main_menu_prompt_is_not_main_command` (added in `de6ca30`) covers this gate.

---

## Honesty statement

All keys driven on a real session against a real TWGS server. No mock, no blind-key, no invented classify. The offer was visually confirmed before pressing E. The explore progress counter advanced live and reached completion. No leg is inferred — each is directly observed from tmux pane capture.
