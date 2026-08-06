# WO-CANON-DRAFT-DAEMON-LIFECYCLE-NO-COVERAGE

**Status:** OPEN (in PR)  
**Priority:** MED  
**Claimed-by:** impl-aiclient-cursor  
**Source:** Cycle-36 / queue-aiclient.md

## Goal

Document shipped `daemon_lifecycle.py` (presence vocab, budgets, quit-stop invariants) in
`canon/architecture/session-engine.md`. Module previously had zero canon hits.

## Tip-verify (2026-08-06 @ main `ba68e50`)

| Check | Result |
|---|---|
| Module | `daemon_lifecycle.py` ~200 lines LIVE |
| Prior canon | session-engine had UX lifecycle rule only; no module/vocab/timeouts |
| Grep | zero `daemon_lifecycle` / `PRESENCE_ONLINE` hits in `canon/` pre-edit |

## Diff

- Expand **App-owned daemon lifecycle** in session-engine.md
- Citations [8] adds the module

## Accept

- [ ] Presence kinds + at-most-one ONLINE + budgets + single-stop-on-confirm named
- [ ] Tip quit copy aligned (`Stop daemon and disconnect …? y/N`)
- [ ] No product code change

## live-prove

`n/a` — canon staging of shipped client helpers.
