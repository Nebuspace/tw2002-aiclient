# WO-P2-OPS-VERB-B — tw do + tw send + tw read (CLI wire, slice B)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-24 · tip **`a9d40bd`** (Cursor)
> Type: build · Phase: 2 · Seat: impl-aiclient-cursor
> Refs: `WO-P2-OPS-VERB-SURFACE.md` slice B · `canon/architecture/control-and-escalation.md`

## Goal
Wire CLI `tw do` / `tw send` / `tw read` (slice B) — settle wait + control_lock aware. If protocol lacks `do`/`send`/`read`, implementing daemon dispatch in `session/` (protocol + daemon handlers) is in scope for slice B.

## Scope
- `tw2002_aiclient/session/cli.py` (+ thin helpers)
- `tw2002_aiclient/session/protocol.py` / `daemon.py` if dispatch needed
- FakeSession/isolated run-dir tests
- README Verb reference + `_SHIPPED_VERBS` / `test_cli_log.py` allowlist
- `WO-P2-OPS-VERB-SURFACE.md` slice-B tick

## Constraints
- No screens/cockpit; no spectate/attach; no new deps
- Path-leak green; case-sensitive wait_prompt
- Full `pytest tests/` green

## Accept
1. `do`, `send`, `read` on `./tw --help`
2. Unit/FakeSession proof (settle-wait + control_lock aware)
3. README + allowlist updated same commit; full suite green

## Proof
help + targeted + full suite. Hub Accept + Push GO @ 13:25:37Z.

## Refs
`WO-P2-OPS-VERB-SURFACE.md` slice B · settle/control_lock canon · hub Accept `a9d40bd`
