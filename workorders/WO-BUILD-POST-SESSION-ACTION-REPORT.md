# WO-BUILD-POST-SESSION-ACTION-REPORT — Post-session app-action accountability digest

> Status: READY (HANDOFF 2026-08-05T23:03:49Z)
> Refs: `canon/DECISIONS.md` post-session-action-report DOC-GAP · `canon/engine/trace-ledger.md`

## Goal

Build the post-session action report Max named: human learns later by a report of what
`app` did autonomously. Fifth ledger consumer; never a live-decision input.

## Delivery choice

**CLI-invocable `tw report`** (primary) + optional `--out PATH` file artifact.
Why: pull-based matches the ledger doctrine; operators can review mid-session or after
exit without depending on process-exit hooks. Session-end can call the same formatter later.

## Scope

- `tw2002_aiclient/session_report.py` — build/format/write
- `tw report` CLI verb
- Optional `rule_id` / `target_player` stamps on ledger `record_do` (omit when unknown)
- Canon: fifth consumer section in `trace-ledger.md`
- Tests

## Accept

Report lists every app-attributed dispatch: taught-rule id (or `?` when unstamped),
target screen (`settled_class`), timestamp; PvP `target_player` when stamped.
