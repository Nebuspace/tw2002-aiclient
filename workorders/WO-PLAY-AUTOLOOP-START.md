# WO-PLAY-AUTOLOOP-START — Play can arm a taught loop (adapter + confirm)

**Status:** OPEN · READY  
**Posted:** 2026-07-27T20:10:00Z · hub — money-path after teach wire tip-check (067–071 already on main)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `b2e586d` · daemon `autoloop_start` LIVE · teach Record/Trigger scaffolds DONE  
**Refs:** `canon/architecture/app-autopilot-model.md` · `session/protocol.py::_dispatch_autoloop_start` · explore-arm pattern in `app.py` / `adapters.explore_start*`

## Goal

From **Play**, after ensure @ a classified screen the operator can **confirm-to-arm** and start a **taught** autoloop (named macro / loop id), without inventing a new CLI verb as the demo path.

Today: daemon has `autoloop_start`; adapters expose stop/pause/status/relaunch only — **no** `autoloop_start` adapter; Play cannot arm a grind the way it arms explore.

## Scope

1. **Adapter:** `adapters.autoloop_start(...)` — typed result, never-raises transport, mirrors explore/autoloop_* style; payload matches `_dispatch_autoloop_start` (macro/loop identity fields the daemon already accepts — do not invent new protocol keys).
2. **Play arm:** confirm-gated offer (reuse `begin_arm_confirm` / armconfirm) that calls the adapter on `y` — honest label (what will replay / which loop). Default-deny.
3. **Tests:** unit/FakeClient for adapter · pin that start path does not bypass confirm · existing explore E path unchanged.
4. **No** priority-engine / chain finder port · **No** `canon/` Accepted-prose invent · **No** `autoloop_resume` word.

## Constraints

- Money path: confirm-gated; never silent-arm on ensure (`no_auto_arm` stays).
- Secrets doctrine unchanged.
- Disjoint from CC `#114` NORM docs and `#93` PARKED.
- If daemon requires a specific loop id / path arg, fail closed with typed error when missing — do not guess.

## Accept

1. `adapters.autoloop_start` exists and round-trips daemon success/failure as typed `AutoLoopResult` (or sibling).
2. Play can offer → confirm → start a taught loop when a valid loop identity is available (fixture or sacrificial profile artifact).
3. Cancel / `N` does not start.
4. Explore `E` path still green (extreme pins / unit).
5. PR + STATUS with SHA · suite green.

## Proof

Unit + FakeClient; optional live on sacrificial profile. live-prove: product path → ≥3 hosts diversity bar if live; else honest n/a with reason only if pure offline fixture Accept (prefer live once).

## Tip-check (hub)

- `adapters.py`: `autoloop_stop|pause|status|relaunch` present; **`autoloop_start` absent** — real.
- `session/protocol.py`: `autoloop_start` dispatch LIVE.
- P5-067…071 code on main — do **not** rebuild teach scaffolds.


**HANDOFF:** EXEC slice · Cursor · 2026-07-28 hub (bank was #116; implement on this branch).
