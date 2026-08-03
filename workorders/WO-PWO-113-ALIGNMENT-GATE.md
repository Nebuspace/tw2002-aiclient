# WO-PWO-113-ALIGNMENT-GATE — Refuse PvP-aggression rule proposals

> Status: **DONE** · origin `f5e3b18` (#344) · seat `impl-aiclient-cursor` · Accept 2026-08-03  
> Type: product safety gate · PWO-113  
> Tip base: `40b8d8a` → merged `f5e3b18`

## Goal
Teacher/rule pipeline rejects PvP-harm proposals at the write/promote/bridge choke — not coach prose, not fire-time toll alone.

## Scope
- A: `tw2002_aiclient/alignment_gate.py` (pure refuse)
- B: wire `rules/writer.write_draft` + `promote_draft` + `cockpit/draft_approve.bridge_to_kernel_document`
- C: `tests/test_alignment_gate.py` (four DoD pins + corp-toll negative)
- D: ULTRACODE + P9 PREP tip → **LIVE**

## Constraints
No LLM teacher. No `classify.py` player_attack invention beyond denylist strings. No `fighter_toll_policy` changes. 092 held.

## Accept
1. `write_draft` refuses PvP aggression — no draft file
2. `promote_draft` refuses hand-edited PvP draft — blessed empty
3. bridge refuses PvP screen + attack macro
4. corp-toll (`fighter_toll` + `do=a`) still writable

## Proof
`pytest tests/test_alignment_gate.py` (+ writer/draft_approve regression) green.
