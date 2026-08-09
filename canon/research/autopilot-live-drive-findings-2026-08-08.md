---
type: Research
title: Autopilot Live-Drive Findings — 2026-08-08
description: Evidence-grade findings from a live-drive research pass against a crawl_sacrificial profile, exercising the Trade Loop Chain, autopilot credit-growth, and purchase-flow axes.
tags: [research, live-drive, autopilot, trade-chains, sacrificial]
timestamp: 2026-08-08T06:30:00Z
---

# Scope and setup

WO-LIVE-DRIVE-AUTOPILOT-RESEARCH (human directive 2026-08-08: assemble a 30+ WO tranche from
live-drive research). Authorization: `CLAUDE.md:63` (post-#545) + `canon/doctrine/dev-drive-exception.md`.

**Profile:** `scout_academy` (`config/profiles.toml`), `crawl_sacrificial = true` — confirmed via
`credentials.is_crawl_sacrificial("scout_academy")` gate now live (PR #546, merged `999ddc7`).
**Server:** catalog key `academy_of_tradewars`, live TCP-probed before connecting. **Character:**
Lieutenant J.G. Sextant, same character as an earlier session's credit-doubling attempt (baseline
continuity below matches its logged 97,809-credit state).

**Session establishment:** `tw ensure --profile scout_academy --timeout 45 --json` → `"ok": true`,
`"classification": "main_command"`, 11 automaton steps. Baseline captured:

| Field | Value |
|---|---|
| Credits | 97,809 |
| Turns left | 34,045 |
| Sector | 24,426 (uncharted space; port: Viking Major, Class 6 BSS) |
| Fighters | 99 |
| Total holds | 10 (Organics=10) |
| Ship | Mammongam Scout Marauder ("SextantShip") |

# Axis 1 — Trade Loop Chain lifecycle

**[GAP] `tw chains --world-id academy_of_tradewars` returns `no_tradeable_hops`** with an empty
`chains` list — chain discovery has no port-price data to search over for this world. This is a
downstream consequence of the explore-axis finding below, not a defect in the chain-discovery logic
itself: discovery is honest about having nothing to search (it does not fabricate a chain), but the
world model behind it was never seeded.

Command/output (`--json`):
```
{"world_id": "academy_of_tradewars", "chains": [], "reason": "no_tradeable_hops", "detail": null, "adapter_note": null, "search_note": null, "truncated": false}
```

`tw chain start`/`tw chain status` (arm/run/abort) were not exercised — there is nothing to arm
without a discovered fingerprint. **NOT-ATTEMPTED**, blocked by the Axis-5 (explore) finding.

# Axis 5 (moved first — it blocks Axes 1–4) — sector explorer session-continuity gap

**[BREAKS] `tw explore start` halts immediately (`distinct_sectors=0`, `sends_issued=0`) with
reason `halt_not_drivable:game_select`, on a daemon session that `tw status`, queried moments
later, still reports as `connected: true` / `classification: "main_command"` with live HUD data
(credits/turns/sector all present and correct).**

Reproduction, in order, same daemon (`run/` dir unchanged throughout):
```
$ tw ensure --profile scout_academy --timeout 45 --json
{"ok": true, ..., "classification": "main_command", "credits": 97809, "turns_left": 34045, ...}

$ tw explore start --world-id academy_of_tradewars --min-sectors 8 --turn-budget 40 --dock-new-ports --json
{"ok": true, "started": true, "running": true, "run": {..., "distinct_sectors": 0, "sends_issued": 0, ...}}

$ tw explore status --json      # polled repeatedly, ~90s later
{"ok": true, "running": false, "run": {"outcome": "halted", "reason": "halt_not_drivable:game_select", "distinct_sectors": 0, "sends_issued": 0, ...}}

$ tw status --json               # same daemon, same run/ dir, immediately after
{"ok": true, "connected": true, "classification": "main_command", "credits": 97809, ...}
```

`sector_explore.py`'s `start()` spawns its own driver thread (`self._run`) against the
**same session object** the daemon already holds — `_dispatch_explore_start` (protocol.py:680)
calls `runner.start(...)` where `runner = server.sector_explore`, no new `Session(...)` construction
anywhere in that path. So this is not literally "a second connection" (that theory was floated
mid-investigation and is **not what the code does** — noted here so a follow-on WO doesn't waste
time re-checking it). What actually classified as `game_select` at the moment `_run`'s gate-check
(`_gate_screen`, `sector_explore.py:289`) ran is the open question: either a stale terminal-buffer
read, a screen transition triggered by the explorer's own first probe send, or a genuine reconnect
inside `_run` not visible from this trace. **This finding is evidenced (the halt is real and
reproducible with the exact commands above) but the root cause inside `_run` is not yet isolated —
that isolation is the WO seed below, not resolved in this research pass.**

### Post-fix status (2026-08-09)

**Mitigated on tip** by `WO-DIAGNOSE-EXPLORE-HALT-GAME-SELECT-LIVE-SESSION` /
PR #554: explore waits out an in-flight guardian reconnect burst before
accepting `halt_not_drivable:*` (see
[Exploration Policy](/strategy/exploration-policy.md) § Session continuity).
Sacrificial credit-doubling live-prove the same day completed
`tw explore start … --dock-new-ports` (`outcome=completed`, distinct sectors
ingested). Residual risk: a halt that persists *after* the burst clears, or a
deadline expiry while `guardian.reconnecting` remains true, still halts
unchanged — that is intentional fail-closed, not a reopen of the false
`game_select` race. Canon contract for same-session reuse is
`WO-CANON-DRAFT-EXPLORE-SESSION-CONTINUITY`.


Consequence: `--dock-new-ports` never ran, so no port price data was ever ingested — this is the
reason Axis 1's chain discovery came back empty, and the reason Axes 2–4 below are NOT-ATTEMPTED
rather than exercised.

# Axis 2 — Automatic credit doubling

**NOT-ATTEMPTED.** Reason: the intended approach was `tw explore --dock-new-ports` to seed port
price data, then `tw chains`/`tw chain start` to run a discovered, human-confirmed loop
unattended and log numeric credits before/after per leg — the standard, evidenced path this WO
asked for. That path is blocked by the Axis-5 finding above. A manual `tw do`-by-hand alternative
(hand-drive individual buy/sell legs without chain-arm) was considered but declined within this
pass's time budget: it would produce real numeric before/after data, but for one arbitrarily-picked
port pair rather than the autopilot's own chain-selection logic, which is a materially different
(and less useful) claim than "the autopilot doubles credits." Left for the follow-on WO once Axis 5
is fixed, so the credit-doubling numbers this WO wants are actually about the autopilot, not about
an operator manually re-deriving what the chain-planner should have found.

# Axis 3 — Fighters purchase

**NOT-ATTEMPTED, with one concrete data point.** `tw do "P"` (dock at the current sector's port,
Viking Major, Class 6/BSS) succeeded — real evidence of the port-trade screen:
```
Fuel Ore   Buying     910    100%       0
Organics   Selling   1240    100%      10
Equipment  Selling   1570    100%       0
You don't have anything they want, and they don't have anything you can buy.
You have 97,809 credits and 0 empty cargo holds.
```
This confirms a regular commodity port is NOT a StarDock — no fighters/cargo-hold/ship-purchase
surface exists here. Reaching an actual StarDock requires navigation across sectors, which is
exactly the job `tw explore --intent find_stardock` exists for (Axis-5 finding blocks this). Manual
sector-by-sector navigation via `tw do` was judged out of this pass's time budget (unbounded turn
count, no map). No claim is made about classification or taught-rule coverage for the fighters
venue itself — this is an honest gap, not a negative finding.

# Axis 4 — Cargo-holds and new-ship purchase

**NOT-ATTEMPTED**, same reason as Axis 3 — `stardock_cargo_hold_quote` and
`stardock_shipyard_listing` paths require a StarDock, not reached this session. Also confirmed:
the character is holding 0 empty cargo holds (10/10 Organics) — any purchase test would first need
to sell down cargo, itself blocked by the same port only wanting to sell, not buy, at this stop.

# WO seeds

- **WO-DIAGNOSE-EXPLORE-HALT-GAME-SELECT-LIVE-SESSION** — isolate why `sector_explore._run`'s first
  gate-check classifies `game_select` against a session `tw status` reports as already at
  `main_command` moments later; add a regression test pinning the fix. Blocks chain-discovery,
  credit-doubling, and both purchase axes for any multi-game BBS profile — highest-priority seed
  from this research.
- **WO-BUILD-CREDIT-DOUBLING-LIVE-PROVE** — once the above lands, re-run this WO's Axis 2 with a
  real discovered-chain arm, logging numeric credits per leg to prove (or disprove) unattended
  doubling.
- **WO-RESEARCH-FIGHTERS-CARGO-SHIP-PURCHASE-COVERAGE** — the deferred Axis 3/4 exercise, once
  explore/chain are unblocked and there is a live world model to navigate from.
- **WO-CANON-DRAFT-EXPLORE-SESSION-CONTINUITY** — document, once diagnosed, whatever
  `sector_explore.py` actually does re: session/connection continuity on `start()` — this research
  pass found the observable symptom but explicitly could not confirm the mechanism from the outside.
- **WO-WIRE-DEV-SENDER-CLI-PATH** — cross-referenced from a parallel static-research pass this
  session: `tw do`/`tw send` (protocol.py:1397,1439) hardcode `session.send(..., sender="app")` —
  grep-confirmed zero reachable CLI path to `sender="dev"`. PR #546's `crawl_sacrificial` gate is
  correct but currently unreachable product-side, so the manual half of
  `dev-drive-exception.md`'s authorization is inert until a CLI surface (e.g. a `--sender dev` flag
  on `tw do`, itself re-checking `is_crawl_sacrificial`, never trusting the caller) is built.
  `_record_ledger` (protocol.py:1229) also still refuses `dev` — a second, independently-tracked
  residual (already named in `dev-drive-exception.md`'s own Code divergence section), not folded
  into this WO seed since it's a distinct decision (attribute vs. refuse) rather than a missing
  code path.
