# WO-PLAY-AUTOLOOP-START — Play can arm a taught loop (adapter + confirm)

**Status:** DONE · tip-check 2026-07-28 (Cursor · #200) — Accept already satisfied on `main`  
**Posted:** 2026-07-27T20:10:00Z · hub — money-path after teach wire tip-check (067–071 already on main)  
**Seat:** `impl-aiclient-cursor`  
**Depends:** `main` ≥ `b2e586d` · daemon `autoloop_start` LIVE · teach Record/Trigger scaffolds DONE  
**Refs:** `canon/architecture/app-autopilot-model.md` · `session/protocol.py::_dispatch_autoloop_start` · explore-arm pattern in `app.py` / `adapters.explore_start*`

## Goal

From **Play**, after ensure @ a classified screen the operator can **confirm-to-arm** and start a **taught** autoloop (named macro / loop id), without inventing a new CLI verb as the demo path.

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

## Tip-check (hub · bank #116)

- Then: `adapters.py` had stop/pause/status/relaunch; **`autoloop_start` absent**.
- `session/protocol.py`: `autoloop_start` dispatch LIVE.
- P5-067…071 scaffolds — do **not** rebuild.

## Tip-check (Cursor · #200 EXEC · 2026-07-28)

**Finding:** Accept 1–4 already green on `main` (implementation landed via prior squash of
`wo/PLAY-AUTOLOOP-START` tip `41b7522` — that tip SHA is not an ancestor of `main`, but
the blobs are). No product code change in this PR.

| Accept | Evidence on tip |
|---|---|
| 1 adapter | `adapters.autoloop_start` @ `adapters.py:273` · `tests/test_adapters_autoloop_start.py` |
| 2 L→Enter→y | `app.py` `pending_confirm_action == "loop"` → `adapters.autoloop_start` · `tests/test_play_chains_arm.py` |
| 3 N / cancel | same module — gate clears, start not called |
| 4 explore E | `pending_confirm_action == "explore"` pin + cross-fire pins in `test_play_chains_arm.py` / #120 |
| Offline proof | `pytest` on adapter + play/cockpit chains/armconfirm modules `-n0` → **115 passed** |

**live-prove:** `n/a` — offline fixture Accept met; this seat has no `config/secrets.json` for a
≥3-host live arm this turn. Prefer live on a later sacrificial profile when credentials are present.

**Out of scope held:** no protocol invent · no silent arm · no `autoloop_resume`.


**HANDOFF:** EXEC slice · Cursor · 2026-07-28 hub (bank was #116; tip-check closed on this branch).
