# WO-XENO-FINGERPRINT

**Status:** OPEN · READY · investigate-first · Claude Code lane · queued after fence 3A
**Posted:** 2026-07-26 · from the live-ensure diagnosis (`4f7449f`)

## Goal

`twgs.exiled.org` — **the operator's own host** — stalls at `unknown`@step 6, and unlike the other two
failures it carries **no recognisable fingerprint at all.** Identify what the screen is. **A fix is not
assumed.**

## The evidence

Captured from the main checkout under Max's explicit GO, one ensure attempt, pre-flight `mode: app`
(nobody attached). Reproduced the hub's error byte-for-byte:
`login_failed:automaton_stuck:classification='unknown':step=6`.

Double-capture with an independent settle between:

```
frame1: 1999 chars  md5=9acb27084705  classification=unknown
frame2: 1999 chars  md5=9acb27084705  classification=unknown
settle between: settled_reason=timeout
=> IDENTICAL — stable, NOT mid-paint
```

Structural markers against `classify.py`'s own regexes:

| marker | xeno |
|---|---|
| `_TWGS_BANNER_TITLE_RE` | ✗ |
| `_TWGS_BANNER_VERSION_RE` | ✗ |
| `_TWGS_BANNER_REGISTERED_RE` | ✗ |
| `login name is required` (micro's fingerprint) | ✗ |
| `ENTER for none` | ✗ |
| `Selection` | ✗ |
| digit-token title (a-net's fingerprint) | ✗ |
| box-drawing present | ✓ |
| non-empty rendered rows | 21 |

**No TWGS banner signal, and neither sibling's fingerprint.** A 21-row box-drawn screen the taught set has
never seen.

## Scope

- **Phase 1 — identify.** What IS this screen? A BBS door menu, a news/announcement page, a
  press-any-key gate, something else? Work from the captured frame under `/tmp/xeno-capture-20260726/`.
- **Phase 2 — only if Phase 1 justifies it.** Propose the smallest honest change.
- **NOT** a new `screen_class` without a **second Max GO**. That gate is explicit and has not been given.

## The outcome that is explicitly acceptable

**"This screen cannot be classified without inventing a class, and halting is correct."**

If that is the truth, **say it and stop.** The product's central promise is that it plays only taught
screens; a host presenting an untaught screen SHOULD halt. An honest N-of-M report — *ensure works on
these hosts, this one presents something we have never been taught* — **satisfies the bar's intent**,
where a fabricated class would satisfy its letter and destroy its point.

## Constraints

- **Max's live session.** Any further live interaction is one-shot and needs his GO; the capture already
  taken is sufficient for Phase 1. Do not drive his daemon to explore.
- No invented classes. No fabricated mode/ARM strings. No default-daemon restart.
- Redact any frame that reaches a committed artifact; frames live under `/tmp` or redacted `audit/`.

## Accept

The screen is **named** (what it is, why the automaton meets it at step 6), **and** either a proposed
smallest-honest-fix or an explicit, argued *"cannot classify without invent — halting is correct."*

## Proof

STATUS + SHA · the identification with evidence · if a fix is proposed, its exact file:line and why it
does not require a new class · no product change without the Phase-2 gate being met.

## Refs

`audit/live-ensure-stall-diagnosis-20260726.md` (Addendum) · capture at `/tmp/xeno-capture-20260726/` ·
hub HANDOFF 2026-07-26T12:51:54Z · Max GO 2026-07-26T12:09Z (capture only)
