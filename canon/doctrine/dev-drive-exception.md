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
  by hand indefinitely.
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

This is a **canon-only ruling today.** Nothing in the codebase implements or gates this exception
yet:

- `tw2002_aiclient/ledger.py`'s `VALID_SENDERS` is still exactly `("app", "human")`
  (`ledger.py:13,143,154-156`) — there is no third sender value, so an action taken under this
  exception cannot currently be logged as anything but `human` (if sent via `tw do`/`tw send`) or
  left unlogged (if sent some other way). That is a real gap against this document's own "logged
  as what it is" requirement.
- There is no code-level check anywhere that confirms `crawl_sacrificial = true` before permitting
  a manual send — the constraint above is currently enforced by operator discipline only, the same
  way every hard rule in `CLAUDE.md` is enforced before its own tooling exists.
- A follow-on WO would need to: add a third `VALID_SENDERS` value (e.g. `"dev"`), gate any send
  path exercising it behind an explicit `crawl_sacrificial` check read from `config/profiles.toml`,
  and ensure it is never reachable from any autopilot/taught-rule/macro path. Until that WO lands,
  this exception is authorized but not yet mechanically enforced — an agent exercising it today is
  relying on the same operator discipline the rest of this codebase's hard rules already rely on
  pre-tooling.

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
