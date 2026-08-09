---
type: System
title: Macros — Taught Keystroke Sequences (record & deterministic replay)
description: A macro is the unit a rule's do plays — a named parameterizable keystroke sequence captured from human demonstration and replayed deterministically, validating each step and halting the instant reality diverges.
tags: [engine, macros, record, replay, halt-on-divergence, start-anchor, send-and-confirm, human-demonstrated, per-world, deterministic]
timestamp: 2026-07-23T20:10:52Z
---

A macro is the smallest reusable unit of *doing* in the trainer: a named, ordered sequence of
keystrokes — each paired with the screen it expects to land on — captured by watching **the human
play**, and later replayed **deterministically**, one confirmed step at a time, halting the moment
the game disagrees with what was recorded. It is the thing a rule's `do` actually issues (see
[Rule–Macro Engine](/architecture/rule-macro-engine.md)); the rule decides *when*, the macro is
*what gets pressed*.

Two invariants govern everything below, and they are the whole reason this concept exists rather
than a bare "replay these keys" loop:

1. **Human-demonstrated substrate — never AI-generated live.** Every macro's steps came from a human
   hand at the keyboard (or, for a mined proposal, from the deterministic ledger-miner). A **recorded**
   demonstration lands **blessed by default** — the capture itself is the approval (Max ruling
   2026-07-26: blessed-by-default is OK; do not require a second promote step for `tw record`).
   **Mined / AI-authored** proposals stay **drafts** under `_drafts/` and fire only after a human
   promotes them into the blessed store. Replay presses back exactly what was taught; it never
   reasons, never invents a keystroke, never asks an LLM what to do next. The AI has no live seat
   here — its only relationship to a macro is as a retrospective author of a *draft* the human must
   bless (see [AI Teacher](/engine/ai-teacher.md)).
2. **Never fire an unverified or destructive send.** A macro validates the world *before* its first
   send (start-anchor) and confirms the screen *after* every send (send-and-confirm), and it
   **stops** rather than pressing on the instant either check fails. Blind pumping — issuing the next
   keystroke against a screen it has not positively confirmed is the one it thinks it is looking at —
   is the exact failure this concept is built to make impossible.

# Schema

## What a macro is

A macro is a named document with an ordered list of **steps** and a **start-anchor**. Each step is:

| Field | Meaning |
|---|---|
| `input` | The keystroke(s) to send for this step (e.g. `"P"`, `"158"`, `""` for a bare Enter/accept-default). |
| `wait_prompt` | An optional regex naming the screen shape this send should produce — the positive confirmation target. Case-sensitive (a mismatched pattern silently times out, never errors — see the Hard Rules). Most recorded steps carry none. |
| `expected_post_class` | The screen *classification* recorded live at capture time (e.g. `port_trade`, `main_command`) — one of `classify_screen()`'s own emitted classes ([Screen Understanding](/engine/screen-understanding.md)), never an invented finer-grained label. Replay re-classifies the settled screen and compares. |

The document also carries:

| Field | Meaning |
|---|---|
| `name` | The macro's identity within its world's library. |
| `start_anchor` | The sector the human was standing in when the sequence was recorded — the precondition every replay re-checks against the *current* sector before pressing anything. |
| `source` | `recorded` (captured from a human `tw record` window — lands **blessed by default**; `--draft` opt-out writes `_drafts/`) or `mined` (a deterministic candidate proposal — see [Candidate Mining](/engine/candidate-mining.md); always draft / inert until a human promotes it). |
| `created_ts`, `mined_stats` | Provenance / the profitability stats a mined proposal was ranked by. |

## Capture — recording the human's demonstration

A capture window is bracketed by `tw record start [name]` … `tw record stop`. While it is open, **every
keystroke the human plays is appended as a step** — its input, the screen classification it produced,
and (when the human supplied one) a `wait_prompt` shape. `stop` writes exactly one artifact: the saved
macro, stamped with the `start_anchor` sector the human was standing in when recording began.

Capture honors the same redaction contract as the rest of the system: a `--secret` send (a password,
or anything flagged secret) mid-capture has its **plaintext replaced with a `REDACTED_SENTINEL`
placeholder**, not dropped outright — the step itself is kept (preserving the macro's step-count and
sequencing) but the keystroke bytes never are. A credential must never live in a file that gets
pressed back; the resulting screen rows are kept verbatim (RX is not redacted — only the TX
keystroke).

The recording is a *human demonstration*, full stop. There is no live AI in the capture loop. Saving a
recorded macro blesses it by default (`LoopRecorder.save(blessed=True)`; CLI `--draft` for the inert
path). A mined macro (`source: mined`) is the one non-recorded origin — the deterministic profit-miner
proposing a recurring profitable ledger subsequence as a **draft** — and that draft becomes fireable
only when a human promotes it into the blessed store.

## Parameterization — generalizing the numbers

A macro is meant to be *reusable*, which means the concrete numbers a human typed during one
demonstration (a hold count, an offer, a sector id) should be able to generalize into named parameters
bound at replay time (e.g. `{qty}` → `50` on one run, `100` on another) — this is now real on both
sides of the round trip; see the Code divergence note immediately below for the shape it landed in.

> **Code divergence (re-verified 2026-08-08, WO-BUILD-MACRO-CAPTURE-PARAM-GENERALIZATION-2:
> parameterization now exists on BOTH sides — the prior entry recording "nothing on either side" is
> superseded).** In tip, `LoopRecorder.step(..., param="qty")` (`tw2002_aiclient/loops/recorder.py`)
> is the opt-in capture half: the caller (today, `tw record`'s per-step manifest `"param"` key) names
> which step's all-digit `keystrokes` to generalize, never a guess. The literal value becomes that
> parameter's recorded default (the document's own `params` object) and the step's `input` becomes the
> placeholder `{name}`; the two never coexist on one step. `replay_loop` (`tw2002_aiclient/loops/player.py`)
> resolves every placeholder through `_apply_params` immediately before the send it gates — an explicit
> `params=` argument outranks the macro's own recorded default — and validates every step's placeholder
> resolvable **at entry, before the first observation**, refusing (never guessing, never sending the
> literal text `"{qty}"`) if any is unbound. A macro that never opts in replays exactly as it always did;
> every non-parameterized step's `input` is untouched. Recorded, not silently conformed. (Pre-rebirth
> port-source: archived `twclient/skills.py`.)

## Deterministic replay — one confirmed step at a time

`tw replay <name>` re-issues a macro's steps in order and returns the per-step trace on full success.
For each step, in order:

1. **Send-and-confirm the keystroke.** The send routes through the session's send-and-confirm path
   with the step's `wait_prompt` as the confirmation target (or an idle-plus-stability fallback when
   the step has none). This is a *positive* confirmation: it returns `confirmed=False` on any desync —
   a settle that only *looks* quiet mid-transition, or a target shape that never actually arrived.
2. **Treat an unconfirmed send as a surprise.** If the send was not positively confirmed, replay
   **halts immediately** — it does not then try to classify a screen it already knows is untrustworthy.
3. **Re-classify and compare.** On a confirmed settle, replay classifies the new screen and compares
   it to the step's `expected_post_class`. An `unknown` classification, or any mismatch against what
   was recorded, is a divergence.
4. **Halt on divergence — never blind-pump.** Any of the above surprises stops the run then and there,
   carrying the full trace up to and including the failing step. Replay never presses the *next* step's
   send against a screen that disagreed with the recording.

Because the game is a live world that may have moved since the macro was taught, halting is the *normal,
correct* outcome whenever reality no longer matches — not an error to suppress. A halted macro hands the
moment back for escalation (see [Control & Escalation](/architecture/control-and-escalation.md)); it
never guesses its way forward.

## Replay-safety invariants (the two scars)

Two live incidents are burned into this concept as named guards. Both are prescriptive: a macro that
cannot honor them does not replay.

### Start-anchor — refuse on context mismatch

A macro's steps only make sense from the sector they were recorded in. A live incident once replayed a
macro verbatim **from the wrong sector** and warped the ship off into a stale sector. So before the
first send of *every* replay invocation (and therefore before every cycle of a repeating run), replay
reads the current sector and validates it against the macro's `start_anchor`:

- **Anchor present but the current sector differs** (or can't be read at all) → a live "reality
  disagrees with the recording" surprise → **halt** (a start-anchor divergence, `step_i = -1`). This
  is exactly the near-miss the guard exists to prevent, and it is **not** bypassable by force — forcing
  past a *detected* mismatch is the danger itself.
- **Anchor absent** (a legacy macro saved before anchor tracking existed, `start_anchor: null`) →
  there is nothing to check against, so it **refuses to replay by default**. The only way past is an
  explicit force — a deliberate operator override, never a silent unanchored replay.

### Send-and-confirm — never auto-fire an unverified prompt

The other scar is the **−75-alignment colonist misfire**: a send issued against a screen that only
looked settled mid-transition, answering a prompt that was not the prompt it thought it was — a
destructive, unverified action fired blind. The fix is structural and applies to every step: a send is
issued and then its result is **positively confirmed** before anything downstream trusts the screen.
An unconfirmed settle is itself a surprise that halts the run. This is what lets a macro *not* auto-fire
an unverified or destructive prompt: it can only ever act on a screen it has confirmed is the one it
expects, and if it cannot confirm, it stops and escalates rather than pressing on.

Together the two invariants realize the fixed constraint: **start-anchor confirms the world before the
first keystroke; send-and-confirm confirms every keystroke's result before the next.** A guard may
always STOP and hand the human the keyboard instead of firing — stopping is a legitimate, first-class
outcome, not a failure mode.

## Per-world library keying

Sectors, ports, and routes are properties of *one game world* — a macro recorded on one server is
meaningless (and, via its start-anchor, unusable) on another. Macros are therefore stored per world,
keyed by the world's identity, so a `start_anchor: 158` means sector 158 *of this world* and a macro
named `ore-run` resolves to the one taught in the world it belongs to. The keying convention itself is
owned by [World Identity](/engine/world-identity.md); this concept simply requires that a macro library
is world-scoped, never a global namespace shared across servers.

## Ledgering a replay

Every step a macro replays is a real send with a real economic effect, so each produces a
[Trace-Ledger](/engine/trace-ledger.md) row attributed to `actor = trainer` (a deterministic, no-LLM
engine send — distinct from `ai`, the live-LLM path, and `human`, a direct operator keystroke), tagged
with the run's `session_id`. This is what keeps a replayed buy that moved thousands of credits from
being an invisible, unaccounted action — the ledger sees macro replays exactly as it sees any other
play. (A replayed step is deliberately *not* tagged as a fresh capture; it is a replay of an already-
captured macro, not a new recording.)

## The repeating posture — where a macro *keeps* running

A macro can be declared `scope: repeating` — a background posture where its sequence loops (a pair-trade
that runs cycle after cycle until a stop condition). The macro *definition* and its per-step safety
(start-anchor re-checked every cycle, send-and-confirm every step, halt-on-divergence) live here. The
**run-loop that arms, drives, and bounds that repetition** — the human-arm gate, the stop-on-unknown
mid-run contract, the depletion-guard that **STOPs and escalates rather than autonomously rotating** to
a new target — is owned by [App Autopilot Model](/architecture/app-autopilot-model.md). This concept guarantees each
*step* is safe; the autopilot model guarantees the *loop around them* stops on the unknown. That
boundary is deliberate and not restated here.

# Examples

## A recorded macro (illustrative)

Every `expected_post_class` below is a real class `classify_screen()` can actually return — there is
no finer-grained class for "the sell-quantity sub-prompt" or "the offer sub-prompt" specifically. The
quantity question ("How many holds of Fuel Ore… [12]?") classifies `money_prompt`; the offer/negotiation
screen that follows is not separately claimed (`Your offer [N] ?` is deliberately left to
[Auto-Haggle](/engine/auto-haggle.md), never to `money_prompt` — [Screen
Understanding](/engine/screen-understanding.md)), so it keeps the port's own `port_trade` content-anchor
identity instead of earning a class of its own:

```
name: ore-run          world: <this world's identity>     source: recorded
start_anchor: 158
steps:
  - input: "P"    wait_prompt: null            expected_post_class: port_trade
  - input: "S"    wait_prompt: null            expected_post_class: money_prompt   # "How many holds...?"
  - input: "50"   wait_prompt: "offer"         expected_post_class: port_trade     # offer/negotiation screen
  - input: ""     wait_prompt: null            expected_post_class: main_command   # accept-default
```

## Replay that halts on divergence

```
tw replay ore-run
  step 0  send "P"   → confirmed, class port_trade   ✓ matches
  step 1  send "S"   → NOT confirmed (the quantity screen never settled)
  → HALT (reason: confirm_failed) — trace returned through step 1; steps 2-3 never sent
```

## Replay that halts on a start-anchor mismatch

```
tw replay ore-run          # ship is currently in sector 231, not 158
  start-anchor check: current sector 231 ≠ anchor 158
  → HALT (reason: start_anchor_mismatch, step -1) — nothing sent; force does NOT bypass a detected mismatch
```

# Findings — code divergences (docs win)

Recorded per the reborn contract: where current code diverges from the target vision, the divergence is
noted, not conformed away.

- **Autopilot's per-cycle EV select vs stop-on-unknown.** The broader autopilot run-loop historically
  selected a live action per cycle by expected-value ranking over the current screen (a
  priority-engine-driven "keep driving / never idle" posture) rather than replaying only *taught*
  screens and STOPping on the unrecognized. Macro replay itself already halts on surprise (correct); the
  divergence lives in the run-loop that wraps it and is owned/recorded by
  [App Autopilot Model](/architecture/app-autopilot-model.md) — flagged here because a `scope: repeating` macro is
  what that loop drives.
- **The 78-turn haggle misfire.** A verified live incident where the port-negotiation resolver
  auto-fired across ~78 turns of an unattended autopilot run — a real money-path defect and the
  archetype of the "auto-fire an unverified action" class this concept's send-and-confirm invariant
  exists to prevent. The guarded-resolver contract that hardens it is owned by
  [Auto-Haggle](/engine/auto-haggle.md) / [Action-Safety Guards](/doctrine/action-safety-guards.md); it is
  cited here as the money-path precedent for why replay never presses an unconfirmed send.
- **Approval gate is enforced by file location, not an explicit flag — and recorded macros are blessed
  by default (Max ruling 2026-07-26).** A mined/AI-authored draft lives in a separate `_drafts/` area
  and becomes replayable only when a human re-saves it into the blessed library. A human `tw record`
  (without `--draft`) writes straight into the blessed store — the demonstration *is* the approval;
  there is no second promote step. The gate is real for machine-authored provenance and is expressed
  as filesystem location rather than an in-macro `approved` field. (Older prose that said "every macro
  is inert until approved" was wrong for the recorded default path; code already defaulted
  `blessed=True` — this concept now matches.)
- **Capture ships today as a manifest writer, not the live start/stop bracket described above.**
  The *Capture* section above (`tw record start [name] … tw record stop`, keystrokes appended live
  as steps) is this concept's original target design. What shipped (WO-P2-G4-X6, tip `13f34a8`) is
  `tw record <manifest>`: a **daemon-free** writer that reads an **already-assembled** JSON
  demonstration manifest (built by hand or script from real `tw do`/`tw screen --json` output) and
  turns it into a stored macro — there is no live bracket, no `start`/`stop` subcommand, and no
  keystroke-to-step transcription while a session runs. The lane disclosed this as a deliberate,
  correctly-scoped first step and the hub Accepted it as honest; wiring a live `tw attach` session
  directly into the recorder is real, named future work the X6 WO's own scope excluded, not an
  abandonment of the target above — tracked as
  [`WO-AUDIT-BUILD-CLI-LIVE-ATTACH-RECORDER-X6`](../../workorders/WO-AUDIT-BUILD-CLI-LIVE-ATTACH-RECORDER-X6.md).
  See [CLI Verb Surface](/architecture/cli-verbs.md)'s
  Implementation status for the mirrored note and the exact shipped arguments
  (`tw2002_aiclient/loops/recorder.py`, `cmd_record` in `tw2002_aiclient/session/cli.py`).
- **The never-auto-action gate defers §A.2's taught-chain exemption — by design, not by omission.**
  [Screen Understanding](/engine/screen-understanding.md)'s ruled tension-resolution (`DECISIONS.md`
  §A.2, Max carte blanche 2026-07-26) says never-auto-action "means no unattended freestyle, and
  human-armed guarded rules are exempt — auto-haggle and taught quantity chains may answer their own
  shapes." The ruling's forward-looking note ("Harmless until a haggle/trade module lands…") is
  **historical**: tip now ships `session/haggle.run_haggle` + `trade_driver` as the human-armed
  guarded money path ([auto-haggle](/engine/auto-haggle.md)). That does **not** reopen
  `loops/player.py`'s `_gate()` for recorded-macro replay. The shipped replay guard still
  halts on *any* screen classified `money_prompt` unconditionally (`reason: never_auto_action`),
  including a step inside a recorded, human-taught macro — see the illustrative `ore-run` example
  above, and `test_a_macro_recorded_to_answer_a_money_prompt_still_halts_there`, whose own docstring
  calls this "the intended behaviour until the arming substrate exists." Still-open residual is the
  *replay-loop arming attestation* (a human-attested surface that can exempt a taught money step),
  not the absence of a haggle module. Closing this gap is a code change, not a doc one — and it must
  **not** be closed by adding a loop-settable bypass flag to `_gate()` (a `force`-style carve-out for
  `money_prompt`): a flag the replay loop itself could set to answer its own money question would
  **be** the loop arming itself, exactly the self-arming §A.2 forbids. The autoloop wire verb applies
  the same reasoning to its own `force` parameter, refusing it outright rather than merely ignoring
  it, because a socket verb has no way to attest that a human, rather than the loop, is behind the
  request. Whatever surface eventually implements the replay exemption must itself be a
  human-attested one; `_gate()`'s current unconditional refusal is the correct default until that
  surface exists.

# Citations

- Reborn vision (fixed constraints): the human is the sovereign pilot and escalation target; the app
  plays back only taught screens and STOPs on the unknown; live keystroke senders are `{app, human}`
  only; the AI is a retrospective, human-invoked author of *draft* rules, never a live keystroke; every
  rule/macro is human-approved before it can fire; a guard may STOP and escalate instead of firing;
  combat/PvP is human-gated and NPC-only.
- Project canon — the three-actor North Star model (see [North Star](/architecture/north-star.md)); the
  Rule–Macro Engine that owns *when* a macro fires (see
  [Rule–Macro Engine](/architecture/rule-macro-engine.md)); the Hard Rules this concept sits beside
  (secrets never touch logs/argv/repo and every password send is redacted; `wait_prompt` regexes are
  case-sensitive; state anchors to the last match, not the first).
- Reimagined from `knowledge/architecture/autonomy-loop.md` — the record/replay/skill substrate is
  carried and **re-rooted**: the old framing mined *the AI's own keystrokes* into learned loops to
  raise an autonomy ratio; the reborn framing captures *the human's demonstration* and treats replay as
  playing back a taught, human-approved sequence — never AI-generated live. The autonomy-ratio gauge
  that doc paired with attribution is deliberately not carried here; it is recast under
  [Coverage Metrics](/engine/coverage-metrics.md).
- Internal design history — the macro/skill record-replay substrate (DESIGN-v2 §3 item 11b/11d), and the
  three named safety scars: TW-02 (send/settle race, the −75-alignment colonist misfire → send-and-
  confirm), TW-03 (wrong-sector replay → start-anchor), TW-04 (replay-ledgering, `actor=trainer` rows).
- Code modules (plain-text): `tw2002_aiclient/loops/player.py` (replay/play, start-anchor guard,
  halt-on-divergence, parameter substitution, per-cycle stop-loss rails — live successor of archived
  `twclient/skills.py`); `settle.py` (`send_and_confirm` — positive confirmation vs idle-only, the
  stale-pre-send-match guard); `ledger.py` (`actor`/`session_id` attribution, redaction);
  `classify.py` (post-step screen classification); `state_parser.py` (current-sector read for the
  start-anchor check).
- Greenfield tip modules (importable, WO-P2-G4): `tw2002_aiclient/loops/recorder.py` (`LoopRecorder`
  — the shipped X6 manifest writer); `cmd_record` in `tw2002_aiclient/session/cli.py` (the CLI
  wrapper); see [CLI Verb Surface](/architecture/cli-verbs.md) for the full shipped-vs-catalog note.
