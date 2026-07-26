# xeno / exiled `unknown`@login step6 — fingerprint (Phase 1)

**WO:** `WO-XENO-FINGERPRINT`  
**Seat:** `impl-aiclient-cursor` · branch `wo/XENO-FINGERPRINT` @ tip base `c25aafa`  
**Date:** 2026-07-26  
**Ruling:** identify only — **no `screen_class` invent** · **no product edit** · no further live drive of Max’s daemon

No passwords or operator handles in this file. Capture paths under `/tmp` only.

---

## Opened artifacts

| Artifact | Role |
|---|---|
| `audit/live-ensure-stall-diagnosis-20260726.md` Addendum | Prior structural marker table + A==B settle |
| `/tmp/xeno-capture-20260726/frame1.json` · `frame2.json` | Live frames (md5 `9acb27084705`, 1999 chars) |
| `/tmp/xeno-capture-20260726/ensure.json` | `login_failed:automaton_stuck:classification='unknown':step=6` |
| `tw2002_aiclient/session/classify.py` | `_BRACKET_OPTION_RE`, timed-out / game_select detectors |

**Live re-drive:** not attempted (WO: Max’s session is one-shot; prior capture sufficient for Phase 1). Shell no-exit on this seat would block it anyway.

---

## What the screen **is** (named)

**Exiled’s custom TWGS server-level game-select door** — not mid-paint, not a name/password gate, not micro’s blank-reject, not a-net’s boxed `Trade Wars … Game Server` banner layout.

Redacted structural layout (from opened frame; SysOp address redacted):

```
[ large block-character / box-drawn logo; host fragments visible ]
[ SysOp/GameOp: <redacted> ]
───────────────────────────────────────────────────────────────────────────────
 [A] <game title> … Sectors/Turns/Time/MBBS|GOLD …
 [B] …
 [C] …
 [D] Default Stock Game …
 [E] Enhanced Stock Game …
 [X] …
  Z  <game title> …          ← letter without square brackets
────────────────────────────────────[ http://www.exiled.org/twgs ]─────────────
[ Exiled TW2002 ]:[A][B][C][D][E][X][Z][#]:Timed out...
```

**Prompt (last non-blank line):** custom Exiled selection chrome ending in `Timed out...` — the host already timed out waiting for a game letter. Settle A==B with `settled_reason=timeout` confirms a **stable** unclassified door, not a half-painted frame.

**Why the automaton meets it at step 6:** login has already passed earlier gates and is sitting on the **server game door** expecting a taught class so `ensure` can send a letter. Classify returns `unknown` → stagnant rounds → `automaton_stuck`.

---

## Why existing vocab returns `unknown` (not invent)

Marker table from the stall addendum **re-confirmed** against the opened frame + `classify.py`:

| Marker / detector | Result on this frame |
|---|---|
| TWGS banner title / version / registered | ✗ (logo art, not the standard banner trio) |
| `select a game` / `Selection (? for menu):` | ✗ |
| Bare boxed `Game` header cell | ✗ |
| Micro `ENTER for none` / `login name is required` | ✗ |
| `_is_menu` via `_BRACKET_OPTION_RE` | ✗ — options use **square** brackets `[A]`, while the regex only accepts `(A)` / `<A>` |
| `_TWGS_TIMED_OUT_PROMPT_RE` (`^Timed out…`) | ✗ — timeout is a **suffix** of a custom prompt line, not the whole prompt |
| Timed-out helpers that walk up for Selection / `select a game` | ✗ — those phrases are absent above |

So this is a **fourth game-select *shape*** the taught set has never absorbed — same *role* as `game_select`, but none of today’s detectors fire. Fall-through to `unknown` is mechanically correct.

---

## Phase 1 verdict (Accept)

**Named:** Exiled custom square-bracket game-select door with timeout-suffixed selection prompt.

**Cannot classify under today’s taught detectors without either inventing a new class or widening `game_select` / menu recognition.** Under north-star (“play only taught screens”), **halting is correct**. An honest N-of-M bar reading: *ensure reaches `main_command` on taught hosts; this host presents an untaught door shape* — satisfies the bar’s intent.

**Phase 2 (not built; needs Max GO):** smallest honest candidate is **another `game_select` detector shape** (same class name — not a new `screen_class`) covering square-bracket game rows + Exiled-style `[…]:Timed out…` prompt, with the same adversarial stale-scrollback discipline as prior variants. Explicitly **out of this tip**.

---

## Contrast (do not collapse)

| Host stall | Root |
|---|---|
| micro `unknown`@6 | blank-name reject → `login.py` (`WO-MICRO-LOGIN-BLANK-REJECT`, CC) |
| a-net `menu`@5 | banner/title mislabel → fixed via `WO-ANET-BANNER-LAYOUT` |
| xeno `unknown`@6 | **untaught square-bracket game-select door** (this note) |

---

## Accept claim

- Screen **named** with evidence from opened `/tmp` capture + stall addendum  
- Explicit: **cannot classify without invent/widen — halting is correct**  
- No product change · no new `screen_class` · blank-reject left to CC
