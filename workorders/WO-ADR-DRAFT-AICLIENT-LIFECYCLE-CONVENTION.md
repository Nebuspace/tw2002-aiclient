# WO-ADR-DRAFT-AICLIENT-LIFECYCLE-CONVENTION

**Status:** OPEN (in PR)  
**Priority:** LOW  
**Claimed-by:** impl-aiclient-cursor  
**Source:** Cycle-36 / queue-aiclient.md

## Goal

Port Folded / Distributed-fold / Superseded lifecycle (+ re-verify cadence) into
`canon/ADR/index.md` before the ADR count grows past easy retrofit. Source pattern:
`sw2102-docs/ADR/README.md` § Lifecycle — adapted to aiclient OKF `canon/` paths.

## Tip-verify (2026-08-06 @ main `375c21f`)

| Check | Result |
|---|---|
| Prior index | Bare 4-column table; no lifecycle section |
| ADR count | 3 Accepted — still easy to retrofit |
| ADR-001/002 | Already have durable prose homes (session-engine / control-and-escalation) — noted on Index rows without flipping Status to Folded yet (bodies still carry Decision text; fold thinning is optional follow-on) |

## Diff

- Lifecycle section + re-verify cadence on `canon/ADR/index.md`
- Index rows for 001/002 note prose homes

## Accept

- [ ] Lifecycle statuses named
- [ ] No product code change
- [ ] No silent Status→Folded flip without body thinning (deferred)

## live-prove

`n/a` — ADR process doc only.
