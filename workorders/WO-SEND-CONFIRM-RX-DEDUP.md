# WO-SEND-CONFIRM-RX-DEDUP

**Status:** OPEN · Claude Code  
**Posted:** 2026-07-25T20:04:13Z

## Goal

Remove redundant outer `rx_count` / settle guard copy in `send_and_confirm` now that `do` path carries it (banked from do rx-guard STATUS) — **only if** elapsed-accounting tests still green.

## Scope

- `tw2002_aiclient/session/` settle/confirm path
- Existing tests that pin elapsed

## Constraints

- Seven tests pin elapsed accounting — do not break; if dedup disturbs them, STATUS with evidence and STOP (bank again).
- Parked classify untouched.

## Accept

One guard site on the shared path **or** documented why dual remains; suite green.

## Proof

Targeted settle/ops tests + STATUS. Prove before/after elapsed.

## Refs

- do rx-guard STATUS banked note
- Origin tip at post: `e42eb31`+
