---
type: Doctrine
title: Development-Drive Exception — a Third, Sacrificial-Only, Manual Sender
description: A narrow, explicitly-scoped carve-out authorizing an AI agent to send live keystrokes for its own development/debugging purposes — never for play, never on a real account, never unattended.
tags: [ai-safety, live-drive, sacrificial, development, human-approval, exception]
timestamp: 2026-08-07T23:44:00Z
---

Every other doctrine and engine document in this bundle states, without qualification, that live
keystroke senders are `{app, human}` only and that the AI never sends one. That statement is
**still true for play** — nothing here changes who may drive a real account, a taught rule, or an
autopilot cycle. This document records a single, narrow exception Max authorized directly
(2026-08-07): an AI agent developing or debugging this codebase may itself send live keystrokes,
strictly bounded as below, for the sole purpose of proving its own fix works end-to-end.

# Schema

## The exception, precisely

An AI agent (e.g. a Claude Code or Cursor implementer seat working this repo) may act as a
**third, distinct sender** — never folded into `app` or `human` — under **all** of the following
conditions simultaneously:

- **Sacrificial account only.** The profile's `config/profiles.toml` entry must carry
  `crawl_sacrificial = true` (see `canon/architecture/` credential/profile doctrine and
  `config/profiles.toml`'s own header comment). A real/production account, or any profile without
  that flag, is out of bounds for this exception — no exception to the exception.
- **Manual, one action at a time.** The agent sends a single keystroke/decision to resolve a
  specific halt it is trying to debug past, watches the result, and stops. This is never a loop,
  never a taught/armed rule, never an autopilot cycle, and never something the agent leaves running
  unattended. If the agent wants to repeat the same resolution many times, that is a sign the
  behavior should be *taught* (a macro/rule, human-approved per the existing model) — not driven
  by hand indefinitely. **Autopilot/chain execution on a sacrificial profile is a separate,
  already-authorized live-drive path** (witness carte-blanche, Max 2026-07-21) — it is not covered
  by this doctrine's manual-keystroke scope and is not in conflict with it; the two authorizations
  are cross-referenced, not contradictory. This document's own conditions (sacrificial-only,
  development/debugging purpose, logged as what it is) still bound the manual path specifically.
- **Development/debugging purpose only.** The action exists to verify a fix, reproduce a bug, or
  unblock a live-prove pass that would otherwise halt at the exact gap under investigation — never
  to play the game, accumulate credits/turns for their own sake, or substitute for the human's own
  play.
- **Logged as what it is.** Any ledger/log entry produced under this exception must be
  attributable to this sender class, not silently recorded as `app` or `human`. Code enforcement
  for this is a residual — see Code divergence below.

## What this does not authorize

- No autopilot, no macro, no taught rule may be armed under this exception — those remain
  exclusively `app`-fired, human-approved, per every other document in this bundle.
- No real/production account. No exception for "just this once, it's not sacrificial but it's
  low-stakes" — the flag is the only test.
- No unattended session. If the agent is not actively watching and deciding each keystroke, this
  exception does not apply.
- This does not create a fourth live-driving mode in `control_lock.py` (`MODE_AI_PILOT` stays
  retired/do-not-revive per `control-and-escalation.md`) — that enum governs who may drive the
  *product's own* control-lock during normal operation. This exception is about an agent
  *developing* the product from outside that lock, on a throwaway account, not a new in-product
  mode.

## Why sacrificial-only is the load-bearing constraint

Every other safety property in this bundle (protective-by-default conduct, never-auto-action on
money paths, start-anchor/send-and-confirm guards) exists to protect a real account, a real
relationship with other players, and real consequences. A sacrificial account has none of those —
it exists to be spent. Confining this exception to `crawl_sacrificial = true` profiles means a
mistake made while debugging costs nothing but that throwaway character's own progress, never a
real player's trust, credits, or standing. This is the same reasoning that already justifies
`crawl_sacrificial` accounts existing at all (`WO-EXPLORE-AUTOMATION-GATE`) — this document simply
extends "safe to spend automation cycles on" to "safe to spend a developer's own manual keystrokes
on," under the same flag.

# Code divergence

**Send-time gate — tip implemented (`WO-BUILD-DEV-DRIVE-SENDER-ENFORCEMENT`).**
`tw2002_aiclient/session/session.py` now carries the third sender value and its gate exactly as
this document authorizes:

- `VALID_SENDERS = ("app", "human", "dev")` (`session.py:100`) — a real third value, never folded
  into `human`.
- `Session._require_dev_sender_authorized()` (`session.py:925`) is a no-op for `"app"`/`"human"`
  and, for `"dev"`, raises `ValueError` unless the active profile is flagged
  `crawl_sacrificial=true`, checked fresh via `credentials.is_crawl_sacrificial()` on **every**
  call (never cached). Both `send()` (`session.py:942,951`) and `send_raw()`
  (`session.py:995,1041`) run this gate before the byte reaches the wire.
- Tested: `tests/test_actor_attribution.py` exercises both `send()` and `send_raw()` for the
  refusal (no profile marked; profile marked but not sacrificial) and the allow (profile marked
  sacrificial) cases.
- `tw2002_aiclient/ledger.py`'s `VALID_SENDERS` re-export and `record_do()`'s membership check
  match, so a `dev` row is structurally acceptable to the ledger. `record_do()` does not itself
  re-check `crawl_sacrificial` — it relies entirely on the send-time gate above having already
  run, satisfying this document's own "logged as what it is" requirement without a second,
  divergent enforcement point.

**Remaining residual — no reachable product path yet.** The gate above exists but nothing in the
shipped CLI reaches it: `tw do` / `tw send` (`session/protocol.py:1432,1474`) hardcode
`sender="app"`, and the daemon's own ledger-attribution choke point, `protocol._record_ledger()`
(`protocol.py:1264`), still attributes only `actor ∈ {"app", "human"}` and silently declines to
record a `dev` row. So an agent exercising this exception today can only do so by calling
`Session.send()`/`send_raw()` directly (e.g. from a Python REPL or a throwaway script) with
`sender="dev"` on a `crawl_sacrificial` profile — never through the product's own `tw` verbs.
Wiring a real CLI surface (e.g. a `--sender dev` flag on `tw do`, itself re-checking
`is_crawl_sacrificial` rather than trusting the caller) and teaching `_record_ledger` to attribute
`dev` rows are tracked as `WO-WIRE-DEV-SENDER-CLI-PATH` — a real follow-on, not yet landed.

# Citations

- Ruling: Max, direct instruction, 2026-08-07 — "You are OK live driving it if its for the purpose
  of development! Add that to canon!" — scoped via clarifying question to sacrificial-account-only,
  manual one-action-at-a-time, logged as a distinct sender class, never autopilot/real
  accounts/unattended loops.
- Does not alter: [alignment-and-conduct](/doctrine/alignment-and-conduct.md) (`{app, human}` live
  senders for play), [ai-teacher](/engine/ai-teacher.md) (the AI's product-facing role stays
  author-only, never a live driver of the *product*), [trace-ledger](/engine/trace-ledger.md) (the
  `{app, human}` live-sender invariant for logged product actions),
  [control-and-escalation](/architecture/control-and-escalation.md) (`MODE_AI_PILOT` stays
  retired/do-not-revive).
- Related: `config/profiles.toml`'s `crawl_sacrificial` flag and its own header comment
  (`WO-EXPLORE-AUTOMATION-GATE`, Max GO 2026-07-27) — the existing precedent for "safe to spend
  automation on this account."
