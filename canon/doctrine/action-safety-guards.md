---
type: Doctrine
title: Action-Safety Guards — the Never-Fire-Unverified Contract
description: The concrete, byte-level guards that make "no autonomous destructive action" real — the enforcement teeth for the sovereignty invariants the control-and-escalation doctrine declares.
tags: [doctrine, safety, guards, autopilot, macros, haggle, rails, stop-on-unknown]
timestamp: 2026-07-23T20:10:53Z
---

The [control & escalation doctrine](/architecture/control-and-escalation.md) declares *what* must
never happen: no live keystroke is sent except by the App (deterministic, playing only taught
screens) or the human (sovereign pilot); the AI is a retrospective, on-demand teacher that authors
rule DRAFTS and never touches the wire; every rule — human- or AI-authored — is human-approved
before it can fire; a guard may STOP and hand the human the keyboard instead of acting. This
concept is the other half: the *teeth*. It collects the concrete, byte-level guards — scattered
today across the macro replay engine, the deterministic resolvers, the crawl driver, and the
run-loop rails — that turn those invariants from a promise into a property the code structurally
enforces. It does not re-derive the invariants (that is control-and-escalation's job, the single
source); it names the guard that enforces each one and states the guarded contract prescriptively.

The organizing rule is one sentence: **never fire an unverified or destructive action.** Every
guard below is a specialization of it. "Unverified" means the action was chosen off a screen the
code cannot positively identify *right now*; "destructive" means it spends turns, credits, cargo,
or fighters, or triggers an irreversible game event. The guards make the App fail *closed* —
toward STOP-and-escalate — never open.

# The human-approval gate is the spine

Every guard here presupposes the spine: a rule (macro, resolver policy, or mined pattern) is inert
until the human approves it, and an unapproved draft can never reach the wire. That gate is
canonical in [control & escalation](/architecture/control-and-escalation.md) and in the
[rule/macro engine](/architecture/rule-macro-engine.md) — this concept references it, does not
restate it. The guards below are what run *after* approval, on each firing, to ensure that even an
approved rule never acts on a screen it has misread. Approval authorizes a behavior; the guards
verify each individual firing of it.

# Replay/macro safety — start-anchor + send-and-confirm

An approved macro is a recorded sequence of sends. Two independent guards gate every replay so a
macro can never "press through" a reality that has drifted from what it recorded. Both are in the
skill replay engine and are cross-linked from [macros](/engine/macros.md).

- **Start-anchor (TW-03).** Every skill carries the sector it was recorded standing in
  (`start_anchor`). Before step 0 of *every* cycle — not just the first — the current sector is
  read and compared. A mismatch, or a sector that cannot be read at all, raises a halt-on-surprise
  divergence and escalates; it never begins the sequence. A legacy skill saved before this field
  existed has a null anchor and **refuses to replay** unless the caller explicitly waives it
  (`force=True`) — never a silent unanchored run. This is the direct scar-tissue of a near-miss
  where a loop wandered off its anchor sector and kept firing.

- **Send-and-confirm (TW-02).** Every send advances only on a *positive* match of the next
  expected screen, never on a bare idle timeout. A step whose send is never positively confirmed
  raises a `confirm_failed` divergence and halts with the trace-so-far intact. Idle silence is not
  consent: the absence of change is never read as success.

Both faults, and an ordinary post-step classification mismatch, reuse one halt-on-surprise
exception, so a multi-cycle loop treats *any* of them identically — halt, preserve the trace,
escalate — which is exactly right for a loop that quietly wandered mid-run, not only one that
launched badly.

# Deterministic-resolver guarded contract — haggle & toll

The App carries a small set of built-in *guarded rules*: deterministic (zero-LLM, zero-reasoning)
resolvers for narrow sub-dialogues the human has approved the App to handle. Two exist today: the
[auto-haggle](/engine/auto-haggle.md) resolver for the port OFFER sub-dialogue, and the
fighter-toll / Option? resolver. They are the highest-risk guards because they act on the money and
combat paths, so their contract is the strictest.

**Auto-haggle is ON BY DEFAULT — but "on" is not "unguarded."** The reborn recast (operator
ruling, 2026-07-23) is a built-in guarded rule the human approves, shipped *enabled*, with its
hardening **mandatory and non-negotiable** — there is no off-until-proven gate, but there is also
no firing without every guard below:

1. **Fresh-render pre-send gate.** Before the opening read — before round 1's counter is even
   computed — the resolver waits until the screen has positively settled. If it never settles
   enough to read safely, it refuses to parse or act and falls back rather than gambling on a
   transitional render.

2. **Resolution requires positive trade evidence, never "the prompt is gone."** A vanished offer
   prompt is *not* proof of a closed deal. A deal is reported resolved only on (a) a verified
   credits delta consistent with the trade direction (the strongest signal — and the honest
   transacted amount is reported, not the guessed ask), or (b) the *current* line being a
   positively identified resolution shape with genuine acceptance context. The settle layer's
   confirm regex necessarily does a whole-screen search and can match a `Command [TL=` left over in
   stale scrollback from *before* the dialogue was entered; the guard closes that gap by anchoring
   to the true current (last non-blank) line and demanding real acceptance context beside it.

3. **A bare main-command prompt ⇒ `DESYNC_FALLBACK`.** If the only evidence is a bare command
   prompt with no acceptance phrase and no credits-delta, the outcome is an explicit desync
   fallback: `resolved=False`, `final_price=None`. The resolver never *guesses* a price and never
   presses on past a screen it cannot positively identify — it accepts the currently-shown default
   safely or reports the desync, and escalates.

**Fighter-toll resolver.** The Option? toll/combat resolver picks Attack only when the fight is
clearly winnable (few enemies and at least as many fighters aboard), else Retreat, and **never
auto-Pays** — a toll payment is human-gated, requiring an explicit hub GO, never selected by the
App. When the vs-line has scrolled out of view and the counts cannot be read, it retreats
(the safe direction), never attacks blind. Its reserve floor clamps every deploy/sell so aboard
fighters cannot be driven to a level the ship cannot defend from. Combat is NPC-only math; PvP is a
human escalation moment, not an App decision — the conduct boundary is owned by
[toll & defense](/strategy/toll-and-defense.md).

The reserve floor and the "clearly winnable" enemy band are **configurable policy knobs**, not
fixed game facts; their current defaults are small early-game values and portable across servers.
Any concrete per-server stat that would refine them (fighter costs, ship defense caps) is
introspected live, never hardcoded here.

# Read-only, never-commit crawl gate (K3)

The menu crawler that discovers a world's dialogue graph must observe every screen without ever
committing a destructive action. That never-commit guarantee is enforced *outside* the crawler's
own traversal logic, by the live-crawl driver, and is cross-linked from
[menu-map & introspection](/engine/menu-map-and-introspection.md). Two structural legs:

- **Sacrificial-only startup gate.** A live crawl refuses outright — before opening a single
  connection or invoking the session factory even once — on any profile not explicitly flagged
  `crawl_sacrificial`. A crawl only ever runs under the disposable, zero-credit / zero-asset
  character protocol, and this refusal is code-enforced, not a convention a caller could forget.

- **Boundary-aligned abort.** A hub-supervisor abort signal, or a human `tw attach` fencing the
  driver, lands the stop at the next screen boundary — never mid-send. Every candidate keystroke
  the crawl could emit still passes through the crawler's single safe-emit chokepoint; the driver
  adds the abort check *ahead* of the real session factory, so the stop is always clean.

# Structural rails (L4) — turn-budget, stop-loss, hazard, novelty-halt

Above the per-firing guards sit the run-loop rails: hard caps the daemon enforces on any
multi-cycle execution surface (chain runner, background loop-player, explore macro), independent of
caller intent. These are cross-linked from the [app-autopilot model](/architecture/app-autopilot-model.md),
which owns the run-loop; here they are named as safety rails.

- **Turn-budget.** A run cannot exceed a cycle cap regardless of what the caller requests — the
  background loop-player and the skill player both clamp requested cycles to a hard ceiling. A run
  whose turn budget is *unknown* fails closed (skips the budgeted action) rather than proceeding on
  an unbounded assumption.

- **Stop-loss.** A credit floor halts the loop, read from the *strict* last-known confirmed
  balance and fail-closed: an unknown or stale balance HALTs rather than arming an unbounded
  floor — and "unknown or stale" is four distinct codes, not one collapsed label, because each
  wants a different repair. Never observed (`credits_unknown`) and observed too long ago
  (`credits_stale`) are kept separate for the reason [control &
  escalation](/architecture/control-and-escalation.md)'s own catalog enumerates them
  separately: never-observed means the arm sequence never showed a balance at all, stale means it
  did and the run has since drifted away from it. The run-loop guard adds two more, distinct from
  both: an adapter answer that is not a usable balance at all (`credits_unreadable` — e.g. a raw
  tuple or a non-int, never truthiness-tested as if it were a healthy reading), and a genuine
  reading at or below the line (`floor_reached`, the depletion outcome itself, not a desync).
  Cockpit STOP-banner labels for both are LIVE on tip (`cockpit/stopbanner.py` maps
  `credits_unreadable` → "credits unreadable", `floor_reached` → "floor reached"). In
  multiplayer, where a hostile server frame could forge a balance line, arming this stop-loss
  carries a documented forged-balance caveat and its own arming gate.

- **Hazard-halt.** A zero-fighter state, an unrecoverable game-select, or a settle-desync the
  settle layer marks as never-safe-to-proceed all hard-halt the loop to escalation rather than
  press on.

- **Novelty-halt *is* stop-on-unknown at the safety layer.** Every cycle re-validates the screen
  match; the first unrecognized frame halts the loop and hands the human the keyboard. This is the
  reborn vision's central invariant expressed as a rail: the App plays only taught screens and
  STOPs on anything else. It is asserted of the thing that *loops*, not only the thing that decides
  one step — every multi-cycle surface re-checks per cycle and halts on the first surprise.

- **Arm-confirm gate.** A run or loop cannot *launch* until its preconditions are confirmed: the
  arm sequence (login/dock) must have shown a confirmed balance before a floored run will start, or
  a legitimate run instant-dies rather than arming blind. Confirm-to-arm is the launch-time analog
  of send-and-confirm.

# Human-confirmed irreversibles

Some actions are irreversible: Genesis torpedo detonation, a major purchase, planetary
colonization. These are **never** an autonomous competing candidate in any selection loop. The App
may *recommend* one — surface it to the human with its rationale — but the firing is normally a
human-approved one-shot, not an EV candidate the loop can pick on its own. **Carve-out (trainer
default):** StarDock **cargo-hold upgrade** buys under APP-ARMED + `C)argo Hold Upgrade·ON` may
App-arm auto-fire per `RESOLVED-TRAINER-STRIP-AND-GUTTER-20260731` point 6 — soft confirm banked,
not per-action `y`. Ship upgrades, Genesis, colonization, and purchases outside that strip toggle
remain human one-shot. The confirm boundary for colonization is owned by
[planet-colonization](/strategy/planet-colonization.md); hold vs ship purchase boundaries live in
[ship-progression](/strategy/ship-progression.md) and
[mode-line-and-teach-controls](/surfaces/mode-line-and-teach-controls.md); this doctrine states the
general rule they specialize: an irreversible action crosses to the human unless the trainer strip
explicitly arms auto-fire for that kind.

## Genesis confirm-to-send choke-point (tip)

Any future App Genesis *send* must pass through
`tw2002_aiclient/genesis_confirm.py::genesis_send_if_confirmed` — the only approved
choke-point. It reuses `cockpit.armconfirm`'s default-deny `y`/`Y` policy
(`compose_genesis_confirm_line` / `resolve_genesis_confirm_key`). Disposition other
than CONFIRM, a missing/non-callable `send`, or an empty payload returns `refused`
and **never** invokes transport send. Cancel clears the pending arm; another Genesis
requires a fresh arm + confirm (never sticky, never default-yes).

**Option A (shipped):** gate only — no Genesis adapter / stub in-tree.
**Option B (HELD):** stub adapter + end-to-end fire — needs a fresh Max GO
([DECISIONS](/DECISIONS.md) PWO-106 line). Recommendation surfaces
(`formations.py` / `recommend_genesis`) stay RECOMMEND-only until that GO.

# Schema

The guard ladder, from per-keystroke to whole-run, each failing *closed* (toward STOP/escalate):

| Layer | Guard | Fires on | Fail-closed outcome |
|---|---|---|---|
| Per-send | send-and-confirm | any macro/resolver send | positive next-screen match required; else `confirm_failed` halt |
| Per-cycle | start-anchor | before step 0 of every cycle | sector mismatch/unreadable ⇒ halt; null anchor ⇒ refuse unless waived |
| Per-cycle | novelty-halt (stop-on-unknown) | unrecognized screen | halt + hand keyboard to human |
| Resolver | fresh-render pre-send gate | before reading the offer/toll screen | screen not settled ⇒ refuse, fall back |
| Resolver | positive-evidence resolution | offer prompt gone | no credits-delta / no acceptance context ⇒ `DESYNC_FALLBACK` |
| Resolver | never-auto-Pay | fighter toll `P` option | requires explicit hub GO; App never selects Pay |
| Run | turn-budget / stop-loss / hazard | multi-cycle run | hard cap / credit floor / hazard ⇒ halt; unknown ⇒ fail-closed |
| Launch | arm-confirm | run/loop start | preconditions unconfirmed ⇒ instant-die, never arm blind |
| Crawl | sacrificial-only gate | live crawl start | non-sacrificial profile ⇒ refuse before any connection |
| Always | human-confirmed irreversible | Genesis / purchase / colonize | never an autonomous candidate; human one-shot only |
| Always | genesis confirm-to-send | future App Genesis send | only via `genesis_send_if_confirmed`; else `refused` (Option B HELD) |

Every STOP carries a typed reason-code from the escalation catalog owned by
[control & escalation](/architecture/control-and-escalation.md) (unrecognized-screen · guard-STOP ·
desync · depletion · hazard · novelty-halt); surfaces render the label, never free text.

# Examples

- **A loop wanders off its anchor.** A background loop-player is replaying a taught trade macro;
  between cycles the ship ends up in the wrong sector. The start-anchor check at the top of the
  next cycle sees the mismatch, raises a halt-on-surprise, and hands the keyboard to the human with
  a `start_anchor_mismatch` reason-code — instead of firing the recorded sends against a stranger
  sector.

- **A haggle "closes" against stale scrollback.** The offer prompt vanishes, but the only
  post-screen evidence is a `Command [TL=` line left over from before the dialogue was entered. The
  resolver's current-line anchor plus acceptance-context requirement find no genuine acceptance and
  no credits-delta, so it reports `DESYNC_FALLBACK` (`resolved=False`) rather than claiming a deal
  at a price it never verified — the exact defect the 78-turn misfire exposed.

- **A toll with an unreadable vs-line.** The Option? prompt is live but the fighter counts have
  scrolled out of view. The resolver cannot prove the fight is winnable, so it Retreats — never
  Attacks blind, never Pays.

- **An unrecognized screen mid-run.** The App playing a taught loop lands on a screen classify
  cannot name. The novelty-halt rail stops the loop on that first frame and escalates to the human,
  who pilots through it — and, later and on-demand, may invoke the AI teacher to propose a rule
  draft covering it.

# Coverage-map boot gate (PWO-112)

Tip enforces the guard inventory at **product TUI startup**, not only under test.
`tw2002_aiclient/app.py`'s `main()` calls `action_safety.assert_coverage_map_intact()` **before**
`curses.wrapper` — if any inventory row lost its source file, source marker, proof test, or proof
marker, the process prints the assertion and exits **1** (fail closed). `--help` / `-h` stay
exempt so argv help still works offline without touching the map. Claiming the coverage map DONE
without this gate staying green is the hazard the prep doc named; the boot assert is the live
enforcement tooth.

# Code Divergence

*(DOCS WIN: canon is prescriptive; these record where the current implementation diverges from, or
sits in tension with, the reborn target. They are documentation findings — this concept edits no
code.)*

1. **The auto-haggle 78-turn misfire was a real money-path defect.** Live-captured, three distinct
   loss defects: a settle-layer confirm matching a stale scrollback `Command [TL=`; treating "the
   offer prompt is gone" as proof of acceptance with zero trade evidence; and an opening read with
   no freshness gate. The current code hardens all three (current-line anchor + acceptance context,
   verified credits-delta, pre-send freshness gate), and canon above states the guarded contract
   prescriptively. Recorded because the resolver ships **on by default** (operator ruling
   2026-07-23) — the hardening is what makes "on" safe, and it is non-negotiable, not optional.

2. **Archived autopilot per-cycle EV selector vs stop-on-unknown — RESOLVED on tip (do-not-revive).**
   Pre-rebirth `autopilot.py` / `priority_engine.py` selected an action every cycle by expected
   value, with an `EXPLORE_BASELINE_EV` (default ~0.01 cr/turn) "never idle" floor that
   manufactured an explore action rather than halting when nothing productive was known — the
   *opposite* posture from the reborn novelty-halt rail. That never-idle EV-selector lived in
   archived modules now flagged do-not-revive; tip has no `autopilot.py`. Today's
   `EXPLORE_BASELINE_EV` survives only in `tw2002_aiclient/focus_status.py` as a suggestion-only
   FOCUS floor (display `ev_per_turn`; zero autonomous-action consumers). Novelty-halt and the
   historical never-idle floor no longer compete as App behavior on an unknown screen. Canonical
   home of the closed finding: [app-autopilot-model](/architecture/app-autopilot-model.md)
   (citation [6]).

3. **`ai_pilot` live-drive mode — RETIRED on tip (2026-08-04).** Pre-rebirth control-lock exposed
   `MODE_AI_PILOT`; tip `tw2002_aiclient/session/control_lock.py` keeps only
   `{app, human, spectate}`. Guards in this doctrine presuppose the {App, human}-only sender
   set — that invariant now matches tip code. Historical finding + do-not-revive flag live in
   [control & escalation](/architecture/control-and-escalation.md) and [findings](/findings.md) §1.
   (`AUDIT-CANON-DRAFT-AI-PILOT-RETIREMENT-STALE`.)

# Citations

[1] tw2002_aiclient/loops/player.py — start-anchor check (`_check_start_anchor`, TW-03),
send-and-confirm replay gate (TW-02), `ReplayDivergence` halt-on-surprise; cycle hard-cap cousin
is `CYCLES_HARD_CEILING` in `session/autoloop.py` (archived `_MAX_PLAY_CYCLES`)
[2] tw2002_aiclient/session/haggle.py — fresh-render pre-send gate (`settle.wait_until_settled`),
positive-evidence resolution (`_resolution_evidence`, `_evidence_backed_price`, credits-delta),
`DESYNC_FALLBACK`, TW-01 money-path hardening (78-turn misfire)
[3] tw2002_aiclient/session/fighter_toll_policy.py — Option? toll/combat resolver, never-auto-Pay,
reserve-floor deploy/sell clamps, retreat-when-unreadable
[4] tw2002_aiclient/menu/crawl_driver.py — `crawl_sacrificial` startup gate, boundary-aligned abort /
driver-fence, safe-emit chokepoint (via `tw2002_aiclient/menu/crawler.py`)
[5] tw2002_aiclient/loops/player.py — turn-budget / strict-balance stop-loss (fail-closed on any
answer that is not a fresh above-floor balance), hazard/novelty halts, arm-confirm launch gate.
No tip `autopilot.py` — archived EV-select live-drive is do-not-revive.
[6] tw2002_aiclient/focus_status.py — `EXPLORE_BASELINE_EV` suggestion-only FOCUS floor (no tip
`priority_engine.py`; archived never-idle EV appetite is do-not-revive / Code Divergence #2)
[7] tw2002_aiclient/session/control_lock.py — tip modes `{app, human, spectate}`; `MODE_AI_PILOT` retired (resolved Code Divergence #3)
[8] CLAUDE.md — Hard rules (send-path redaction, single-connection daemon, case-sensitive
wait_prompt, last-match state_parser anchoring)
[9] tw2002_aiclient/loops/player.py (`_check_floor`) — the reborn stop-loss guard that actually
ships this rail today, as four distinct fail-closed codes: `HALT_CREDITS_UNKNOWN`,
`HALT_CREDITS_STALE`, `HALT_CREDITS_UNREADABLE`, `HALT_FLOOR_REACHED`
[10] tw2002_aiclient/genesis_confirm.py — Genesis confirm-to-send choke-point
(`genesis_send_if_confirmed`); Option A gate-only on tip; Option B HELD
[11] tw2002_aiclient/action_safety.py (`assert_coverage_map_intact`) + `app.py` `main()` —
PWO-112 coverage-map inventory; boot fail-closed before curses (`--help` exempt)
