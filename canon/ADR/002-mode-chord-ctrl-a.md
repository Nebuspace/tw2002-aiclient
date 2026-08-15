---
type: ADR
title: ADR 002 — Mode Chord Is Ctrl-A (No Printable Mode)
description: Mode toggles App↔Human via Ctrl-A only; bare M while attached is TW Move; Spectate is not a Mode dual seat.
tags: [adr, mode, control, keyboard, batch-1b]
timestamp: 2026-07-25T09:34:00Z
---

# ADR 002 — Mode Chord Is Ctrl-A (No Printable Mode)

Filename convention: `/ADR/002-mode-chord-ctrl-a.md`

---

## Status

**Folded into [control-and-escalation](/architecture/control-and-escalation.md#the-mode-switch)** ·
Accepted 2026-07-25 by Max (Batch 1b + Batch 2/3 · hub GO `@ 09:31:54Z`) ·
_(re-verified 2026-08-15)_

Durable Mode Switch prose lives under [The Mode Switch](/architecture/control-and-escalation.md#the-mode-switch)
and the Mode Line surface. This ADR remains the decision record / pointer.

## Context

Canon and tip product briefly disagreed on the App↔Human Mode key. Early canon named bare `M`.
TradeWars uses printable `M` for Move while the human is flying. Max ruled Batch 1b (2026-07-25):

1. Mode chord = **Ctrl-A** (TTY-reachable; not Ctrl-M / ⌘M).
2. While Human is attached, bare **`M` = TW Move** (passthrough).
3. **No single printable** may be Mode (same collision class as the game alphabet).

Batch 2/3 added: **Spectate is not a Mode**; default run = App/autopilot; Ctrl-] from App-hold =
deliberate no-op stay App.

---

## Decision

- **Mode** (App↔Human both directions, once App can hold the seat) = **Ctrl-A**.
- Attached bare **`M`** reaches the game (Move); it is never Mode.
- Spectate remains observation chrome only — not a third dual position.
- Hint-band / prose that previously said `M)ode` / "`M` leads the band" cite **Ctrl-A** / `^A)ode`.

---

## Consequences

- **Canonical prose home:** [Control & Escalation — The Mode Switch](/architecture/control-and-escalation.md#the-mode-switch)
  (Ctrl-A Mode · attached bare `M` = TW Move · Spectate ≠ Mode · no printable Mode). Sibling
  surfaces (`mode-line-and-teach-controls`, `spectate-and-attach`, `trainer-cockpit`,
  `visual-language`, `index`) cite ADR-002 as the decision record; they do not re-litigate it.
- Product (`WO-P5-061-ENTRY`) **LIVE on tip** — `MODE_KEY` (ASCII 1) toggles App↔Human both
  directions (`screens.py` unattached attach path + `app.py` attached → App-hold). Attached bare
  `M` is Move passthrough. (WO-FIX-ADR-002-COMPLETION-CLAIM-VS-UNCLOSED-SEAM — tip landed; prior
  "docs-win until tip lands" hedge retired.)
- GNU `screen` / common `tmux` Ctrl-A prefixes may eat Mode — operator escape/rebind; no second Mode key.
- DOC-GAP-M-FROM-SPECTATE **SUPERSEDED/CLOSED**.

---

## Refs

Max Batch 1b `@ 09:17:56Z` · Batch 2/3 `@ 09:25:55Z` · hub Max GO fold `@ 09:31:54Z`
