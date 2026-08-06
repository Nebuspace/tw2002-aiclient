# WO-CANON-DRAFT-ALIGNMENT-GATE-DENYLIST-UNCITED

**Status:** OPEN (in PR)  
**Priority:** MED  
**Claimed-by:** impl-aiclient-cursor  
**Source:** Cycle-37 / queue-aiclient.md

## Goal

Make M1's concrete proposal-time mechanism visible in canon: name `alignment_gate.py`, its
screen/do denylists, and the proposal-time vs `fighter_toll_policy` fire-time distinction.

## Tip-verify (2026-08-06 @ main `d7da233`)

| Check | Result |
|---|---|
| Module | `alignment_gate.py` LIVE; wired from `rules/writer.py` + `cockpit/draft_approve.py` |
| Canon M1 | States "no taught rule may encode initiate-PvP" but never names the module / denylists |
| Citations [5] | Listed fighter_toll + control_lock only |

## Diff

- New subsection under M1 in `canon/doctrine/alignment-and-conduct.md`
- Citations [5] adds `alignment_gate.py`

## Accept

- [ ] M1 names the module + denylist shape + proposal vs fire-time split
- [ ] No product code change
- [ ] No new OKF concept file (edit existing doctrine)

## live-prove

`n/a` — canon staging on existing doctrine page.
