# WO-BUILD-REROUTE-VS-FIGHT-EV

**Status:** IN PROGRESS  
**Priority:** MED  
**Gated:** no (hub GO 2026-08-06 Cycle-42 core-mechanics greenlight)

## Goal

Ship a pure reroute-vs-fight EV ranking kernel: compare caller-supplied extra-hop
turn cost vs expected fight cost for priority/coach. Design for eventual `app`
auto-fire behind teach/arm (not a coaching-only ceiling). Never invent hops;
never override the fighter-toll `force_share` / NPC / PvP rails.

## Scope

- `tw2002_aiclient/reroute_vs_fight.py` — `compare_reroute_vs_fight`, `toll_ev_to_status`
- `tests/test_reroute_vs_fight.py`
- `canon/strategy/toll-and-defense.md` — Code grounding tip-stamp + divergence wording

Out of scope (v1): wiring `decide_encounter` to EV; unsupervised path search;
auto-fire execute path (needs taught/armed rule later).

## Accept

1. Kernel prefers `reroute` when cheaper and below auto-Attack gate.
2. Incomplete hops/counts/PvP → `preferred=unknown` + gated.
3. `fighter_toll_policy` does not import the EV module (live rail unchanged).
4. live-prove: n/a (pure ranking offline).

## Proof

```bash
.venv/bin/python -m pytest tests/test_reroute_vs_fight.py -q -n0
```
