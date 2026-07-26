# Live ensure matrix — 2026-07-26 (redacted)

**WO:** `WO-LIVE-ENSURE-MATRIX` · **Seat:** `impl-aiclient-cursor`  
**Isolated config:** `/tmp/tw2002-live-ensure-matrix-20260726T0801Z` (outside tree; never committed)  
**Secrets keys persisted:** `proof_rogue` only (no micro / anet persist)  
**Tip base at close:** ≥ `ca8108a` / `50bbc46`

No passwords, handles, or screen dumps in this file.

## Results matrix

| Server | Letter | NEW | RETURNING | Error type / notes |
|---|---|---|---|---|
| `roguetw.net:2002` | A | **PASS** (`main_command`) | **PASS** (`main_command`) | remote — both cells clean |
| `twgs.microblaster.net:2002` | B | **FAIL** (`unknown`@step6) | **SKIP** (no password persist) | **remote** classify gap · recovery **FAIL** `empty_response` = **local** (daemon socket / stop→re-ensure race) |
| `game.a-net-online.lol:2002` | C | **FAIL** (`menu`@step5) | **SKIP** (no password persist) | first `empty_response` **withdrawn/contested** (sandbox-poisoned artifact discarded — not a host claim) · durable NEW **FAIL** `menu`@step5 = **remote** (login stall / possible game-select↔`menu` misclass) |

**Letter diversity proven:** A / B / C across three hosts (profile-driven `game_letter`, not hardcoded `A`).

## Evidence paths (local `/tmp` only)

| Cell | Artifact |
|---|---|
| rogue NEW | `ensure-rogue-new.json` (`ok=true`) |
| rogue RETURNING | `ensure-rogue-returning.json` (`ok=true`) |
| micro NEW | `ensure-micro-new.json` (`unknown`@step6) |
| micro recovery | `ensure-micro-new-retry.json` (`empty_response`) |
| a-net NEW / recovery | `ensure-anet-new.json` · `ensure-anet-new-retry.json` (`menu`@step5) |
| a-net local empty | `ensure-anet-new-retry.sandbox-poisoned.json` (`empty_response`) — discarded as sandbox-poisoned |

## Optional micro stall frame

**Gone.** No redacted 80×25 capture under `/tmp/tw2002-live-ensure-matrix-20260726T0801Z` (or nearby `/tmp`); `screen_withheld=login_failure` only; `run/` logs empty. Bank follow-up capture WO if corpus needed.

## Open follow-ups (hub 09:38)

1. Classify corpus for micro `unknown`@login step6 (frame if recaptured)
2. a-net `menu`@login step5 vs Selection/`game_select` scout
3. Ensure recovery `empty_response` after stop (readiness wait / distinguish from host) — see `WO-ENSURE-SPAWN-READINESS`

## Hub close

Matrix NEW wave **CLOSED** 2026-07-26T09:38:38Z — no further live ensures without hub GO.
