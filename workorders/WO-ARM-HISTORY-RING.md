# WO-ARM-HISTORY-RING — armed-run sends appear in session history

**Status:** READY · visible automation honesty (follow-on #224)
**Seat:** `impl-claudecode-aiclient`
**Branch:** `wo/ARM-HISTORY-RING`
**Depends:** `main` ≥ `6ea3dcd` (#224 armed run on main)

## Goal

When an armed run sends keystrokes without a human keystroke per send, those
sends must appear in the **session history ring** (or equivalent operator-
visible ledger the CLI/`tw history` path already exposes). Launch proof that
only cites the CLI's own "armed — running" line is a single-source oracle;
after a bad run the operator needs an independent answer to "what did it
actually do on my behalf."

Ordered **before** any WO that widens the armed path (cycles, repetition,
unattended).

## Scope

- Trace where autoloop / `replay_loop` / `session.send*` emits (or fails to
  emit) history/ledger entries during an armed run.
- Make daemon sends during `autoloop_start` → `replay_loop` land in the same
  history surface operators already use for human sends — or document and
  wire the minimal equivalent if the ring is attach-only today.
- Focused test: arm a one-step macro (scripted session), assert the history
  ring / ledger contains that send (input and/or classification as the
  existing schema already records).
- Do **not** invent a second parallel audit log if the history ring can carry
  it.

## Out of scope

- Cycles / repetition / unattended runs.
- §A.2 / `never_auto_action` changes.
- Second door into `_dispatch_autoloop_start`.
- `#218` app.py split.
- `start_anchor` null on planted proof macros (separate, non-blocking).

## Constraints

- No weakening of arm-confirm, revalidation, or player rails.
- History entries must not leak secrets (same redaction rules as existing
  history/status surfaces).
- Prefer the existing history schema; extend only if a typed field is missing
  for App-originated sends.
- Offline suite green; live-prove `n/a` unless this adds a new TWGS path
  (expected: `n/a` — observability of an existing path).

## Accept

1. After an armed one-pass run (test harness), history/ledger contains the
   send(s) the player issued — assertable offline, not by reading the CLI
   arm banner alone.
2. Human attach/send history behaviour unchanged (regression pin).
3. No secret leakage in history payloads (existing redaction pins still green).
4. Full offline `suite` green.
5. STATUS names the exact history API/field used.

## Proof

- Focused offline test: arm → assert ring contains send.
- Full offline `suite`.
- Live-prove: `n/a` (observability; no new send path) unless implementation
  forces a live touch — then Cursor safe-half only.

## Refs

- CC HEADS-UP 2026-07-29T17:41Z (re-rank recommendation)
- Cursor arm proof `.samantha/audit/reflex-armed-run-arm-live-20260729T1736Z/`
- `tw2002_aiclient/session/autoloop.py` · `loops/player.py` · history CLI path
- Max: visible automation — operator must see what the app sent
