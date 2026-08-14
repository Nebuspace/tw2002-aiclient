# tw2002-aiclient — Canon (reborn)

The canonical knowledge bundle for the **human-piloted trainer** vision of tw2002-aiclient: a
human sovereign at the keyboard, an app that deterministically autopilots only the screens it has
been *taught* and STOPS on every unknown, and a retrospective AI that codifies responses into a
growing repertoire — never a live driver. These concepts are **prescriptive**: they are the truth
about their subjects, and code conforms to them (**DOCS WIN** — divergences are recorded as
findings, never silently reconciled). This bundle is a ground-up rebirth that **supersedes the
earlier AI-first `knowledge/` bundle**, which is archived once this one stands complete. Start at
the North Star.

Status: **rebirth in progress** — concepts are authored bottom-up in dependency order. Entries
marked _(planned)_ are not yet written; entries marked ✅ written exist on disk.

# Architecture

* [North Star](/architecture/north-star.md) — The reborn vision: a human-piloted TradeWars trainer whose app autopilots the screens it has been taught, escalates every unknown to the human, and lets an observing AI codify responses into its growing repertoire. — ✅ written
* [Control & Escalation](/architecture/control-and-escalation.md) — The App/Human live control dual (plus read-only Spectate observation), the Ctrl-A Mode toggle, the escalate-on-unknown STOP→handoff, and the enumerated escalation reason-code catalog. — ✅ written
* [Session Engine](/architecture/session-engine.md) — The daemon + one-shot-CLI split that owns the single telnet connection and terminal, serves the JSON verb protocol, and carries every keystroke through the control-lock with an `{app,human}` actor tag. — ✅ written
* [CLI Verb Surface](/architecture/cli-verbs.md) — The single reference catalog of every one-shot `tw` verb: what it does, its arguments, whether it drives / reads / teaches, and which concept owns its behavior. — ✅ written
* [Settle Detection & Screen Readiness](/architecture/settle-detection.md) — How the engine decides a screen has stopped changing and is safe to act on, absorbing known interjections without mistaking them for novel screens. — ✅ written
* [The Guarded Rule–Macro Engine](/architecture/rule-macro-engine.md) — The deterministic reflex unit the app plays — `when(screen_match + guards) → do(macro)`, prioritized and scoped, firing only on taught screens and never guessing. — ✅ written
* [The APP Autopilot Model](/architecture/app-autopilot-model.md) — The runtime that runs a multi-screen taught behavior over many cycles: the run-loop that re-validates every screen, stops on the unknown, and arms only on human confirm. — ✅ written
* [Login Automaton](/architecture/login-automaton.md) — The classification-driven expect/respond automaton that drives a cold socket through BBS interstitials to the Command prompt, with NEW-vs-RETURNING branching over the secure store. — ✅ written
* [Resilience & Reconnect](/architecture/resilience-and-reconnect.md) — The connection-level supervisor that survives a dropped socket via reconnect + login-replay, plus a conservative idle-keepalive that stays off on unsafe screens. — ✅ written

# Engine

* [Screen Understanding](/engine/screen-understanding.md) — Turns a settled rendered screen into `{screen_class, structured game-state}` — the semantic read feeding rule screen-matching, the world-model, and the HUD. — ✅ written
* [World Identity](/engine/world-identity.md) — The single `host + game-letter + character` identity that scopes every durable per-world store. — ✅ written
* [World Model](/engine/world-model.md) — The incrementally-built, persisted per-world sector database every routing, guard, and coaching behavior reads. — ✅ written
* [Game-Data Store](/engine/game-data-store.md) — Two-layer game knowledge: authored portable OKF semantics plus live per-server introspected DATA, never hardcoded stats. — ✅ written
* [Menu Map & Read-Only Introspection](/engine/menu-map-and-introspection.md) — The per-world menu graph, the safety-critical read-only never-commit crawler that builds it, and deterministic menu navigation over it. — ✅ written
* [The Trace Ledger](/engine/trace-ledger.md) — The append-only per-dispatch semantic record with `{app,human}` actor attribution — the single learning, observability, and retro substrate. — ✅ written
* [Post-Session Action Report](/engine/post-session-action-report.md) — The pull-based `tw report` digest of a session's `actor=app` dispatches — accountability for autonomous armed-rule action after the fact, not per-firing approval. — ✅ written (stub — full detail in Trace Ledger)
* [Macros](/engine/macros.md) — Taught keystroke sequences captured from human demonstration and replayed deterministically with halt-on-divergence — the unit a rule's `do` plays. — ✅ written
* [The AI Teacher](/engine/ai-teacher.md) — The human-invoked retrospective AI that reads a screen or escalation moment and proposes a guarded rule DRAFT — never a live keystroke. — ✅ written
* [Candidate Mining](/engine/candidate-mining.md) — The no-LLM machinery that mines the ledger for recurring profitable patterns into human-approved rule and loop candidates. — ✅ written
* [Auto-Haggle](/engine/auto-haggle.md) — The deterministic no-LLM port OFFER negotiation resolver — the archetype of a built-in guarded rule. — ✅ written
* [Priority Engine](/engine/priority-engine.md) — The deterministic strategic layer ranking what to pursue and ordering which taught behaviors run — never a live per-cycle action-picker over unknown screens. — ✅ written
* [Coaching Engine](/engine/coaching-engine.md) — Reads live state + world-model to surface the optimal option and its tradeoffs as a human-facing tip — it teaches options, never silently acts. — ✅ written
* [Coverage & Autonomy Metrics](/engine/coverage-metrics.md) — The recast metric: how much of the *known* the taught app handles versus how often escalation and teaching are needed. — ✅ written

# Strategy

* [Trade Loops & Chains](/strategy/trade-loops.md) — How the app defines, ranks, and runs trade loops and chains by credits-per-turn — as taught human-approved repeating macros with depletion guards that STOP and escalate. — ✅ written
* [Port Economics](/strategy/port-economics.md) — The numeric parameter substrate for trade scoring and trade rule-guards: classification, spread, floor prices, and depletion. — ✅ written
* [Frontier Exploration Policy](/strategy/exploration-policy.md) — When and how much to explore plus the deterministic BFS/frontier planner that writes the world-model — a taught behavior that stops on any unrecognized sector screen. — ✅ written
* [Explore Defensive Posture](/strategy/explore-defensive-posture.md) — Pre-uncharted map-fill gate: judgment fighter-floor / credit / dealer-detour defaults that seek a StarDock dealer then halt for a human-gated buy — pure decision, no send. — ✅ written
* [Toll & Defense Math](/strategy/toll-and-defense.md) — Fight/pay/reroute decision math feeding the fighter-toll guarded rules — NPC targets only; combat is a prime escalation moment. — ✅ written
* [Planet Colonization & Production](/strategy/planet-colonization.md) — Whether/where to colonize plus the production-income model — a recommendation surfaced to the human, with Genesis deploy always a human-confirmed one-shot. — ✅ written
* [Special Formations](/strategy/special-formations.md) — Warp-graph topology detection (dead-end/bubble/one-way/warp-sink) feeding route-hazard guards and colonization siting — LOCATE, CATALOG, RECOMMEND only. — ✅ written
* [Ship Progression & Upgrades](/strategy/ship-progression.md) — When and to what to upgrade holds/ships: holds-first decision-support recommendations and taught behaviors, every purchase human-approved. — ✅ written

# Surfaces

* [The Trainer Cockpit](/surfaces/trainer-cockpit.md) — The framed oversight dashboard: panels, HUD, fold, always-on live state, and what the app is doing. — ✅ written
* [Mode Line & Teach Controls](/surfaces/mode-line-and-teach-controls.md) — The cockpit interaction contract: the App/Human actor indicator, the Ctrl-A Mode chord + A/R/T keys, the operate-the-app control cluster, and how STOP-and-handoff is presented. — ✅ written
* [Spectate & Attach](/surfaces/spectate-and-attach.md) — The two dedicated human-facing surfaces on the one daemon: watch read-only without touching, or take the live keyboard. — ✅ written
* [Entry & Profile Selection](/surfaces/entry-and-profile-selection.md) — The pre-cockpit launcher: pick or create a player and choose the game server from the known catalog. — ✅ written
* [Operator Cold Start](/surfaces/operator-cold-start.md) — Day-to-day cold-start: profiles, secrets placement, Mode/Spectate/Attach chords, run-dir isolation, and stuck-seat recovery. — ✅ written
* [Visual Language](/surfaces/visual-language.md) — The shared color, glyph, box-drawing, liveness-cue, and responsive-fold dictionary every cockpit surface renders through — the surfaces are the sentences, this is the dictionary. — ✅ written

# Doctrine

* [Alignment & Conduct](/doctrine/alignment-and-conduct.md) — The protective-by-default constitution bounding what any rule may do to other players and what the AI teacher may even propose. — ✅ written
* [Secrets & Credential Handling](/doctrine/secrets-and-credentials.md) — The non-negotiable discipline for storing, resolving, redacting, and rotating passwords and credentials. — ✅ written
* [Server Catalog Sources](/doctrine/server-catalog-sources.md) — Public TWGS directory sources, catalog honesty policies, and verified counts for the operator address book. — ✅ written
* [Action-Safety Guards](/doctrine/action-safety-guards.md) — The concrete byte-level guards that make "no autonomous destructive action" real — enforcing the sovereignty invariants control-and-escalation declares. — ✅ written

# Testing

* [Test Case Catalog](/testing/test-case-catalog.md) — Inventory of every pytest case in tw2002-aiclient (**7545** tests · **317** active modules on tip 2026-08-14; **1** BANKED ignore): one-sentence blurb per test, grouped by subsystem; REMOVED/BANKED annotated. — ✅ written


# Research / Interop evidence

* [TW2002 Screen Patterns](/research/tw2002-screen-patterns.md) — Extracted classifier & settle patterns (block titles, quantity prompts, prompt-line settle, missing gates, binary-mining negatives). **Required reading** before classify / settle / screen-understanding tips. — ✅ written

# Decisions & ADRs

* [ADR-001 — One tree, embedded session](/ADR/001-one-tree-embedded-session.md) — Collapses the Phase-0 two-top-level-package scaffold into one `tw2002_aiclient` import tree with the daemon-core under `session/`, plus app-owned daemon lifecycle and an exit-time stop-the-daemon-too confirm popup. — _(Folded into [session-engine](/architecture/session-engine.md) · re-verified 2026-08-06)_
* [ADR-002 — Mode chord Ctrl-A](/ADR/002-mode-chord-ctrl-a.md) — Mode = Ctrl-A; no printable Mode; attached `M` = Move; Spectate ≠ Mode dual. — _(Folded into [control-and-escalation § Mode Switch](/architecture/control-and-escalation.md#the-mode-switch) · re-verified 2026-08-06)_
* [ADR-003 — Discovered-chain approve scaffold](/ADR/003-discovered-chain-approve-scaffold.md) — A discovered ProfitChain arms only through an exact human-approved semantic scaffold plus a separate confirm gate. — _(Distributed-fold: 6/8 · re-verified 2026-08-06 · prose home [trade-loops](/strategy/trade-loops.md))_

See also [`/DECISIONS.md`](/DECISIONS.md) — the live open-questions workspace feeding future ADRs.

* [Findings](/findings.md) — the DOCS-WIN divergence log: recorded code↔canon findings (`ai_pilot` mode · per-cycle EV picker · `{ai,trainer,human}` actor enum · 78-turn haggle) plus a reference index of the archived legacy bundle. — ✅ written

* [Archive Port Patterns](/research/archive-port-patterns.md) — Distilled algorithmic and structural patterns from `archive/pre-rebirth-2026-07-23/` (settle protocol, login automaton, skill record/replay, haggle, world-model store, chain finder, BFS explore, priority engine, cockpit layout, menu crawler, credits discipline, learning dry-run). Must-read before cockpit/autopilot spine, teach A/R/T, settle polish, menu crawl, trade loops, world model, login UX, and priority ranking WOs. — ✅ written

# Conventions

* **Hypothesis-tagging.** Every un-introspected game number carries `tags: [..., hypothesis]` and
  an explicit **Verification status** line; it is a configurable coaching/guard parameter until
  verified against the live game, never a hardcoded fact. The discipline is itself a safety rule.
* **Introspected DATA vs authored SEMANTICS (two-layer rule).** This bundle authors portable OKF
  semantics and schemas only; concrete per-server stat *values* (ship stats, hold prices, item
  catalogs) are introspected live into the game-data store, never hardcoded in canon.
* **Attribution actor set.** Live keystroke senders are **`{app, human}` only**; every ledger row
  and send carries `session_id`. AI is a rule **author**, never a live sender — there is no `ai`
  value for a live keystroke; AI teaching contribution is a separate provenance axis.
* **Per-world keying.** `host + game-letter + character/registration` scopes the world-model,
  game-data store, menu-map, macro/loop library, and retro — stated once in World Identity,
  referenced everywhere; no store invents its own key.
* **Human-approval + on-demand-AI invariants.** Every rule (human- or AI-authored) is
  human-approved before it can fire; the AI teacher proposes only when the human invokes Analyze
  (on-demand-only — proactive surfacing is out of canon). Canonical statement in Control &
  Escalation; enforcement teeth in Action-Safety Guards.
* **Stop-on-unknown is a RUNTIME property.** "Zero reasoning per cycle · stop-on-unknown ·
  confirm-to-arm" is asserted of the thing that *loops* (the APP Autopilot Model), not only the
  thing that decides one step. Every multi-cycle surface re-validates screen-match per cycle and
  halts to escalation on the first unrecognized frame.
* **Escalation is enumerable.** Every STOP carries a typed reason-code from the catalog owned by
  Control & Escalation (unrecognized-screen · guard-STOP · desync · depletion · hazard ·
  novelty-halt); surfaces render the label, never free text.
* **DOCS-WIN divergences are RECORDED, never silently reconciled.** Where code contradicts the
  reborn contract (the `MODE_AI_PILOT` live-drive mode, the per-cycle EV keystroke driver, the
  §22 full-autopilot capstone, the old `{ai,trainer,human}` actor enum, the auto-haggle 78-turn
  misfire), canon states the prescriptive contract and files the code behavior as a finding in the
  owning concept.
* **Public-bound.** The repo is public: no real personal names/handles/FQDN/username appear in
  canon; the human is referenced as "the operator"/"the human". Citations reference the project's
  internal design history and the private design journals **by section in plain text** (never
  URLs); the journals themselves are not part of this bundle.
