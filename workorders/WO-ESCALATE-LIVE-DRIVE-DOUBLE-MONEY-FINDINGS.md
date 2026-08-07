# WO-ESCALATE-LIVE-DRIVE-DOUBLE-MONEY-FINDINGS — orchestrator live-drive, 2026-08-06

> Status: **FINDINGS FILED** — orchestrator live-drive session, not yet built.

## What was asked

Max asked the orchestrator to live-drive tw2002-aiclient's autopilot and see if it could
autonomously double its starting money through trading. This file records what the live drive
found and spawns the follow-on WOs needed to actually get there.

## What the live drive did

1. Read `canon/architecture/north-star.md` (SIGNED Max 2026-07-25) — confirms the project was
   deliberately "reborn" away from an AI-first / fully-autonomous framing into a human-piloted
   trainer. The app never live-drives on its own initiative; it plays back only taught behaviors
   and stops unconditionally on any unrecognized screen. This is intentional design, not a gap —
   noted here so it isn't mistaken for one.
2. Checked `tw loops --world-id <world>` across every world under `state/world/` — every single
   one has exactly one taught behavior, `proof-arm-ping` (a 2-step proof-of-concept). **No trade
   loop has ever been taught or recorded**, in any world.
3. Checked the backend: `tw2002_aiclient/trade_driver.py` + `session/trade_chain.py` implement a
   real trade-loop runner (`run_chain`, depletion-STOP, etc.) and `ULTRACODE-WO-INVENTORY.md`
   marks PWO-101/PWO-102 ("Trade loop define/rank" / "Trade loop run + depletion STOP") **LIVE**
   with a passing `test_trade_driver` suite. The daemon protocol (`session/protocol.py`) wires
   `trade_chain_start` / `trade_chain_stop` / `trade_chain_status` RPC verbs. **But no CLI verb
   exposes any of the three** — `tw --help`'s verb table has no `chain start`/`trade`/equivalent.
   The engine is built and tested; nothing reachable from `./tw` (or any headless script) can arm
   it. Confirmed by grep across `session/cli.py`'s ~30 `add_parser` calls — no match.
4. Actually ran it live: logged into the disposable `scout_academy` profile (`crawl_sacrificial =
   true`, per `config/profiles.toml`'s Max-GO'd sacrificial-trainer block) — pre-existing
   character "Ensign Sextant", 99,000 credits, 29,583 turns, sector 1 (Sol / FedSpace).
5. `tw chains --world-id academy_of_tradewars` → "no priced, routable hops yet" (nothing explored
   yet in this world's state store).
6. `tw explore start --world-id academy_of_tradewars --turn-budget 300 --dock-new-ports` — the
   correct verb to auto-discover and price ports so a chain can be built. Halted almost
   immediately: `outcome: "halted", reason: "dock_report_unreadable"`, 2 sectors mapped, 8 turns
   spent, **credits unchanged at 99,000**.
7. `tw screen` at the halt showed the actual cause: sector 1's port is **Sol, Class 0 (Special)**
   — a StarDock, not a commodity port. Docking there lands on the equipment-purchase menu
   (`Which item do you wish to buy? (A,B,C,Q,?)` — cargo holds / fighters / shield points), which
   the classifier tags `class: unknown`. The port-report parser expects a commodity Commerce
   Report and can't make sense of a StarDock buy-menu, so explore correctly stops rather than
   guessing — but the practical effect is it can never get past sector 1 to find a real
   commodity port to price.
8. Confirmed final state: `credits: 99000` (unchanged), daemon stopped cleanly, no partial state
   left running against the live server.

## Verdict

**No — it cannot currently double its money, for two independent, both-real reasons:**

1. **No taught trade loop exists anywhere** (only the ping proof), so even the "known-behavior
   autopilot" path — the one the reborn design explicitly does support, per
   `app-autopilot-model.md`'s "run only after a human arms it, but then runs multi-cycle" — has
   nothing to arm.
2. **The one backend system built and tested for exactly this (`trade_driver`/`trade_chain`,
   PWO-101/102 LIVE) has no CLI/headless entry point**, so even if a chain were discovered,
   nothing outside the TUI cockpit chrome (Phase 5, needs a real TTY) could arm it.
3. **Independent of both of the above, the live drive hit a concrete classifier gap**: explore
   cannot get past a StarDock (Class 0 Special) port to find commodity ports to price, because
   the buy-menu screen isn't recognized. Sector 1 on a freshly-registered character is very
   commonly a StarDock (federation home sector) — this isn't an edge case, it's close to the
   typical starting condition.

## Follow-on work (scoped, not yet built)

- **WO-BUILD-TRADE-CHAIN-CLI-VERB** — expose `trade_chain_start` / `_stop` / `_status` as a `tw
  chain start|stop|status` CLI verb (mirrors the existing `explore start|stop|status` pattern in
  `session/cli.py` exactly — `send_request("trade_chain_start", payload, run_dir=...)`). This is
  the single highest-leverage fix: the engine already exists and is tested, it just isn't
  reachable. Low risk — a thin CLI wrapper over an already-live daemon RPC.
- **WO-FIX-EXPLORE-SKIP-SPECIAL-PORTS** — `dock_new_ports` explore should recognize Class 0
  Special ports (StarDock) before attempting to read a commerce report, and skip docking there
  (or classify the buy-menu screen as a distinct known type it simply ignores for pricing
  purposes) rather than halting the whole explore run. StarDock never sells commodities, so
  there's nothing to price there regardless.
- **WO-LIVE-WITNESS-FIRST-TRADE-LOOP** — once both of the above ship: re-run this same live drive
  (same or a fresh sacrificial profile), let explore get past sector 1 to a real commodity port
  pair, confirm `tw chains` finds a priced route, arm it via the new `tw chain start` verb, and
  watch it actually run turns and accumulate credits. This is the actual "does it double the
  money" proof — everything above is what's blocking that proof from being attempted at all.

## Owner

gameserver n/a (this is tw2002-aiclient) — `tw2002_aiclient/session/cli.py`,
`tw2002_aiclient/session/trade_chain.py`, `tw2002_aiclient/session/sector_explore.py`.

## Refs

Live session: `scout_academy` / `academy_of_tradewars`, 2026-08-06T02:29-02:30Z UTC. Credits
99,000 → 99,000 (unchanged). `canon/architecture/north-star.md`, `canon/architecture/app-autopilot-model.md`,
`workorders/ULTRACODE-WO-INVENTORY.md` Phase 6/8, `tw2002_aiclient/trade_driver.py`,
`tw2002_aiclient/session/protocol.py:735-777`.
