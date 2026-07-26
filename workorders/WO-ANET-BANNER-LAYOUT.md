# WO-ANET-BANNER-LAYOUT

**Status:** OPEN · READY · product (`session/classify.py`) · Claude Code lane · queued after fence 3A
**Posted:** 2026-07-26 · from the live-ensure diagnosis (`4f7449f`)

## Goal

`game.a-net-online.lol` presents a **fourth real TWGS game-select layout** that `classify.py`'s three
existing detectors do not cover. Close it — **with a fixture and an adversarial pass, the same as every
prior variant got.**

## The evidence — TWO independent barriers, both verified

**Barrier 1 — the title regex.** `_TWGS_BANNER_TITLE_RE` (`classify.py:158`) is
`r"trade\s*wars\s+game\s+server"`: it requires `wars` followed by whitespace then `game`. Measured
directly:

```
'Trade Wars 2002 Game Server'   -> False    <- a-net; the digit token alone defeats it
'TradeWars Game Server'         -> True     <- roguetw (the working control)
'Trade Wars Game Server'        -> True
```

**Barrier 2 — banner proximity.** `_BANNER_PROXIMITY_MAX_LINES = 6` (`classify.py:164`) requires the
three banner signals to sit close together. On this host the plain banner lines are at rendered rows
0 and 2, but the **title is embedded 13 rows down inside an ANSI-art box.**

**Fixing the regex alone is NOT enough** — barrier 2 still rejects it. **Both must move together**, and
the WO fails if only one is addressed.

Double-capture with an independent settle between was byte-identical: **stable screen, not mid-paint.**

**Control:** `roguetw.net` reaches `game_select` in one step with the same code and tip. Its banner has no
digit token, all three lines within 3 rows, no ANSI box — exactly the shape the existing detector handles.
**The difference is host layout, not flaky code.**

## Scope

- `tw2002_aiclient/session/classify.py` — the TWGS banner detectors and their bounds.
- A **captured fixture** for this layout under `tests/fixtures/`, redacted.
- **NOT** `login.py`. **NOT** a new `screen_class` — this is widening an existing detector to a real
  fourth variant, which is a different thing from inventing a class. If your design needs a new class,
  **STOP and escalate** — that requires a second Max GO.

## Constraints — the proximity bound exists for a reason

`_BANNER_PROXIMITY_MAX_LINES` **bounds a stale or forged banner assembled from fragments scattered across
an unrelated document.** Relaxing it is a real loosening of a real guard.

- **Do not simply raise the number until a-net passes.** Argue what the bound protects, and find a change
  that admits this genuine layout without admitting a scattered/forged one — e.g. tying the signals to the
  ANSI box that contains them, rather than to a raw line distance.
- **Re-run the existing adversarial cases.** Every prior variant earned a hardening pass; this one inherits
  that obligation. A widening that passes a-net and weakens the stale-banner defence is a net loss.
- Do not weaken the anchor-to-live-prompt tie that previous hardening added.

## Accept

`ensure` reaches `game_select` on a-net; the three prior variants still classify; **the stale/forged-banner
adversarial cases still refuse.** Fixture committed, redacted.

## Proof

STATUS + SHA · the new fixture · before/after `classify_screen` on all four layouts · adversarial cases
green · full suite from junitxml after exit · isolated live re-run against a-net.

## Refs

`audit/live-ensure-stall-diagnosis-20260726.md` · `classify.py:158,164,397-484` · hub HANDOFF 2026-07-26T12:51:54Z
