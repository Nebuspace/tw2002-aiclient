# WO-P5-061-ENTRY — Ctrl-A entry chip APP (Mode entry-point hardening)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **EXECUTED / DONE** 2026-07-25 · tip **`420430d`** (CC · Fable 5; stacked log_note `4280d8a`) · Accept #2 CLOSED
> Type: harden · Phase: 5 · Seat: impl-claudecode-aiclient
> Refs: `WO-P5-060-072-mode-teach-PREP.md` §PWO-061 entry · `canon/architecture/control-and-escalation.md` · ADR-002

## Goal
061 entry hardening — two REVISEs landed: (1) dual `_MODE_KEY` eliminated (screens → app single source confirmed); (2) test no longer claims Ctrl-] UNRULED after Max ruled it. Entry chip = APP (match daemon `MODE_APP`, not SPECTATE — Max @ 09:33:23Z). Three stale-literal findings banked from the review.

## Scope
- `tw2002_aiclient/screens.py` — single `MODE_KEY` source
- `tw2002_aiclient/app.py` — entry chip = APP
- `tests/` — Ctrl-] honesty pin corrected; isolation 1896/0/0 cert
- `canon/ADR/002-ctrl-a-mode-switch.md` — Accept #2 close

## Constraints
- Ctrl-] from App-hold = deliberate no-op (stay App); must be documented+pinned, not "UNRULED"
- Single `_MODE_KEY` — no duplication (REVISE fix)
- Entry chip = `APP`, not `SPECTATE`

## Accept
1. Entry chip = `APP` (matches daemon `MODE_APP`)
2. Single `_MODE_KEY` source (screens → app); Ctrl-] no-op stay-App pin
3. Full suite isolation 1896/0/0 cert-to-commit green

## Proof
Accept #2: isolation 1896/0/0 · cert-to-commit md5 green · Ctrl-] no-op pin · single MODE_KEY grep.  
tip `420430d` on origin (log_note stack `4280d8a`).

## Refs
`WO-P5-060-072-mode-teach-PREP.md` §PWO-061 entry · ADR-002 · hub Accept #2 @ 09:57:30Z
