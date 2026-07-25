# WO-P2-OPS-VERB-F1 — tw attach CLI (thin, no curses)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`e243bc2`** (Cursor)
> Type: build · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-P2-OPS-VERB-F-PREP.md` F1 · `canon/surfaces/spectate-and-attach.md`

## Goal
Wire `tw attach` CLI over existing daemon `_handle_attach` (TTY · keystroke forward · release on exit). Thin port of archive `interactive_app.py` (~294) or rawer client if curses color deferrable. control_lock single-writer honored. `spectate` stays off help.

## Scope
- `tw2002_aiclient/session/cli.py` (`tw attach` sub-command)
- Optional thin module under `session/` (new `interactive_app.py` or equivalent)
- Rehab `tests/test_attach_protocol*.py` (greenfield, drop `twclient`)
- `_SHIPPED_VERBS` allowlist + README/WO

## Constraints
- No spectate (F2 HOLD); no redaction extras (F1b follow-on)
- No chrome / no inventing second control path
- control_lock single-writer
- Full suite green; `spectate` stays off help

## Accept
1. `tw attach` on `./tw --help`
2. FakeDaemon/protocol attach proof (TTY + keystroke forward + release on exit)
3. Allowlist + README updated
4. `spectate` not on help

## Proof
Targeted + full suite. Hub Completeness 95 / Quality 94 / Safety 95 / Craft 93 → SHIP.

## Refs
`WO-P2-OPS-VERB-F-PREP.md` F1 · archive `interactive_app.py` · hub Accept + Push GO @ 14:40:37Z
