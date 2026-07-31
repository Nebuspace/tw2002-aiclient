# WO-PLAY-HELP-AUTONOMY-KEYS

**Goal:** Teach / help / strip copy names the early-game autonomy keys
that already work on tip (`E` explore · `H` hold · `O` offer · `L` chains).

## Why

Full-autonomy offline kernel shipped (#267–#280) but operator discovery
still depends on muscle memory. Ada would miss `O` entirely. Surface the
affordances where help already lists Play keys.

## Fix

1. Find the existing Play help / teach / strip strings that list key
   bindings.
2. Add honest one-liners for `O` (offer top FOCUS → confirm), `H` (hold
   buy confirm when scaffold complete), keep `E`/`L` accurate.
3. Pins: help text contains the new labels; no new arm paths.

## Accept

1. Help/teach surface mentions `O` and `H` with confirm-not-auto wording.
2. No daemon/adapter changes.
3. live-prove **n/a** (copy-only).

## Scope

- help / cockpit teach / status hint strings (whichever is canonical)
- tests
- `workorders/WO-PLAY-HELP-AUTONOMY-KEYS.md`

## Constraints

- Display/copy only · no silent arm · no new deps

## Proof

Offline string/RTL pins. live-prove **n/a**.

## Refs

- #280 autonomy offer · #279 hold arm · `.samantha/plans/full-autonomy-early-game.md`
