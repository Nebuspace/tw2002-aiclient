---
type: System
title: Candidate Mining — Deterministic Rule & Loop Proposals from the Ledger
description: The no-LLM machinery that mines the trace ledger for recurring profitable patterns and proposes them as inert human-approved rule and loop drafts — it ranks candidates to offer, never picks a live keystroke.
tags: [mining, candidates, deterministic, drafts, session-retro, human-approval, profit-per-turn, prescriptive]
timestamp: 2026-07-23T20:10:53Z
---

Candidate mining is the trainer's deterministic proposal engine. It reads the passive
[trace ledger](/engine/trace-ledger.md) — nothing else — and looks for input-subsequences that
recurred and paid, then writes each one out as an **inert draft** for the human to review and bless.
No language model is involved at any step; it is a bounded sliding-window count over a small JSONL
file, a scorer, and a draft writer. It is the deterministic sibling of the
[AI teacher](/engine/ai-teacher.md): both feed the same human-approval surface, and the two are kept
split precisely along the LLM-versus-deterministic seam. This concept is prescriptive — it specifies
what mining reads, how it groups and ranks, that its output is always a draft that fires nothing, and
the one property that separates it from the counter-canon it must never become: **it ranks candidates
to propose, it does not score an action to play.**

# Schema

## What it reads, what it emits

Mining is a pure read of the ledger and a pure write of drafts. It never touches the live connection,
never sends a keystroke, never edits game state.

| | |
|---|---|
| **Input** | A slice of the append-only ledger (`state/ledger.jsonl`) — the same rows the trace-ledger concept defines. A slice can be the whole ledger, a named `tw record` capture, or a session/timestamp window. |
| **Unit mined** | A contiguous **input-subsequence**: a window of consecutive `do`/`send` rows, e.g. the buy-then-sell steps of one trade round. |
| **Output** | Zero or more **draft** macros written to `state/skills/_drafts/`, each carrying its mined stats and its start-anchor. A draft is inert: it cannot fire until a human promotes it (`save_skill(..., draft=False)`). |

The dividing line is absolute and load-bearing: mining **proposes**, the human **approves**, and only
then does the [rule/macro engine](/architecture/rule-macro-engine.md) let the app play the result.
Mining's own act of writing a draft to disk is not arming anything — an unapproved draft is exactly
as inert on disk as it was as a pattern in memory.

## The profit-miner — grouping and ranking

The miner slides every window length in a bounded range over the ledger slice and groups occurrences
by the key `(pre_class, input-tuple, post_class)` — the screen it started on, the exact keystroke
sequence, and the screen it ended on. A group that recurs at least `min_support` times becomes a
candidate pattern; groups below the support floor are discarded as noise.

Two grouping rules are deliberate, each earned from a live money-loop defect:

- **Numeric inputs are wildcarded to `<NUM>` for grouping only.** A real port *always* haggles, so the
  quantity and offer steps of an otherwise identical buy-then-sell loop carry a different literal
  number every single occurrence (146 credits one round, 158 the next). Matching on raw input text
  therefore never recurs at the step that actually carries the profit — either the window includes the
  ever-changing numeral (support stuck at 1, filtered out) or excludes it (support recurs but the
  credits look like zero). Collapsing bare numerals to `<NUM>` lets the *shape* of the loop group while
  the real observed values are preserved in the sample steps. Reward math is unaffected: profit always
  comes from the row's `reward` field, never from the input text.
- **A redacted step disqualifies the whole window.** Any window containing a `<redacted>` input (a
  password send) is skipped entirely — a pattern built on a secret is never mined and never replayable.

**Ranking is profit-per-*turn*, frequency-aware.** Each group is scored by its average credits-per-turn
(`Σ d_credits / Σ turn-cost`, where a turn's cost is `-d_turns` since turns are spent, not gained),
falling back to credits-per-*action* when no occurrence of that window ever consumed a turn. Patterns
sort richest-first. Turn-rate leads because it is the trainer's real currency: **400 cr over 5 turns
beats 500 cr over 10 turns** — the same cr/turn scorer the [priority engine](/engine/priority-engine.md)
uses to order behaviors, applied here to rank proposals. Frequency enters both as the support floor
(a candidate must recur) and, in the session-retro ranking below, as a `cr_per_action × support`
tie-break so a pattern that both pays and recurs outranks a one-off windfall.

## Start-anchor parity — never a rootless replay

Every mined pattern carries a **`start_anchor`**: the sector the window's first row was standing in
before its own input was sent. This is the same start-anchor semantic a human-recorded capture
persists, threaded through so a mined draft is guarded by the *same* pre-send anchor check as a
recorded one. A mined trade loop is just as replayable-from-the-wrong-sector as a hand-recorded one;
without the anchor it would silently default to the unanchored legacy path. This is the miner honoring
the trainer's **never-fire-unverified** invariant at authorship time: a proposal is born with the
context a guard needs to refuse it if the world has moved (the start-anchor half of the
start-anchor-plus-send-and-confirm contract; see [action-safety-guards](/doctrine/action-safety-guards.md)).
A row that lacks a sector (an older row, a fixture predating the field) yields a null anchor — never an
invented one; only read, never fabricated.

## Session retro — `tw analyze`

Session retro is the human-facing front of the same machinery: `tw analyze <session>` reads one
session's ledger slice, runs the identical miner over it, keeps only the profitable recurring patterns,
and ranks them as **"recurring profitable decisions — candidates to codify as trainer behavior."** It
is the loop's back half: after a session of play, the operator asks *what did I (or the app) do
repeatedly and profitably here that is worth teaching once instead of re-deciding every time?* — and the
retro answers with a ranked, human-readable list, each candidate showing its support count, its cr/turn
(or cr/action), its pre→post classification, and its keystroke steps.

Session is a soft key while the ledger has no first-class session field: an exact `tw record` capture
name, a timestamp prefix, or `all`. The retro's ranking adds frequency to the profit sort
(`cr_per_turn`, then `cr_per_action × support`, then raw support) so the list favors patterns that are
both lucrative and habitual — the ones most worth spending an approval on.

## Loop candidates — the longest profitable chains

The richest class of candidate is a **trade loop**: the longest input-subsequence that closes a
profitable cycle. Mined and proposed exactly like any other pattern, a loop candidate becomes, once
approved, a **taught repeating macro** — a `scope: repeating` behavior the app steps deterministically,
matching a screen-guard each cycle. Its defining safety property is prescriptive and non-negotiable:
**a loop's depletion is a STOP-guard, never an autonomous rotation.** When the port that made the loop
profitable is exhausted, the taught macro does not silently hunt for a new one — it stops and hands the
keyboard back to the human (or surfaces the exhaustion as an escalation). Rotating to a fresh loop is a
new decision, and new decisions belong to the human or to a separately-approved behavior, not to a
running macro improvising. The run-loop that actually orchestrates a taught chain and owns that STOP on
depletion (and on any unrecognized screen) lives in the
[app autopilot model](/architecture/app-autopilot-model.md); mining only *proposes* the chain and the
[trade-loops](/strategy/trade-loops.md) strategy defines how chains are scored and ranked.

# It ranks candidates — it does not score a live action

The single most important thing candidate mining is **not**: it is not a live scorer picking the next
keystroke each cycle from its own history. That shape — a store read to *drive* play, an EV number
chosen per tick over whatever screen is showing — is the retired counter-canon the reborn trainer
forbids. Mining ranks a *catalog of proposals for a human to approve*; it produces drafts that sit inert
until blessed and, once blessed, become deterministic behaviors that themselves stop on anything they
were not taught. The output of mining never becomes a live keystroke by any path that skips the human:

- **Draft, always.** Mining's product is a draft macro. A draft fires nothing. Only human promotion
  turns a draft into a fireable behavior — the same approval gate the AI teacher's proposals pass
  through, distinct only in that mining's author is deterministic and the teacher's is a language model.
- **No proactive arming.** Mining does not watch for a chance to arm a rule; it runs when the human runs
  it (`tw patterns` / `tw mine` / `tw analyze`). Even its convenience of writing the top drafts to disk
  in one call is a convenience of *authorship*, not of activation — the drafts are inert.
- **A guard may still refuse.** An approved mined macro carries its start-anchor and screen-guard; if the
  world has moved, the guard STOPs and escalates rather than replaying blind. Approval is permission to
  *offer* the behavior to the app, not a promise it will fire regardless of context.

This is why mining and the [AI teacher](/engine/ai-teacher.md) are kept as two concepts rather than
merged: they share the approval surface and the draft contract, but one is a bounded deterministic count
and the other a retrospective, human-invoked language-model reconstruction. The seam is clean — LLM
versus no-LLM — and canon keeps it (Operator ruling, 2026-07-23: *ai-teacher / candidate-mining → keep
split*). Mining's drafts are a mechanism entirely separate from the teacher's on-demand proposals and
are unaffected by the teacher-only ruling — a fact worth stating because both land in the same review
inbox.

# Examples

Every class named below is one `classify_screen()` actually emits ([Screen
Understanding](/engine/screen-understanding.md)) — the offer/negotiation step keeps the port's own
`port_trade` content-anchor identity rather than earning a class of its own, the same reason
[Macros](/engine/macros.md)'s own illustrative recording does.

```
Ledger slice (illustrative — a trade round repeated across a session):
  port_trade   input "T"    → port_trade      reward {}
  port_trade   input "158"  → port_trade      reward {d_credits: +230, d_turns: 0}
  port_trade   input "M4223"→ sector_display  reward {d_turns: -1}
  ... (the same three-step shape recurs 6× this session, offer numeral varies) ...

Miner groups on (pre_class, <NUM>-normalized input-tuple, post_class):
  key = (port_trade, ("T", "<NUM>", "M4223"), sector_display)   support = 6

Ranked candidate:
  #1  n=6   ~230 cr/action  [port_trade → sector_display]   "T" → "<NUM>" → "M4223"
      start_anchor: sector 4223
      → written as an INERT draft at state/skills/_drafts/mined-0-T__NUM__M4223

tw analyze <session> surfaces it as:
  "recurring profitable — candidate to codify as trainer behavior"

Nothing fires. The human reviews #1, and only `save_skill(..., draft=False)` promotes it into
a taught repeating macro the app may then play — start-anchored, depletion-STOP-guarded.
```

# Code divergence

The reborn frame above — mining proposes inert drafts, ranks candidates but never scores a live action,
and stays split from the teacher — is largely what `miner.py` and `analyze.py` already implement (the
`<NUM>` wildcard, the cr/turn ranking, the redaction skip, the start-anchor threading, and the
draft-only output are all present and correct). The divergences are in framing and in a sibling module,
not in the miner's own safety:

- **`analyze.py` still carries the pre-reborn "AI vs trainer" retro framing.** Its output note says *"AI
  vs trainer split sharpens after TW-05"*, and the source concept (`autonomy-loop.md`) described the
  retro as *filtering to the `actor=ai` decisions specifically*. Under the reborn vision there is **no
  live `ai` actor** — the retro mines recurring profitable input-subsequences regardless of a live-AI
  attribution, because the only live senders are `{app, human}` (see [trace-ledger](/engine/trace-ledger.md)).
  The current code is in fact already actor-agnostic (it mines all rows, not an `ai` slice), so the
  divergence is only the stale *note* promising an AI/trainer split that the reborn model retires. Docs
  win: the retro's job is "recurring profitable decisions worth codifying," not "AI decisions worth
  codifying."

- **The counter-canon mining must never become is live in a sibling autopilot.** Mining itself correctly
  ranks-to-propose, but the same cr/turn scorer is, in the current codebase, also wired into a
  per-cycle live action-picker: `priority_engine.recommend_actions()` used as a keystroke driver and
  `autopilot.select()` choosing an action each tick (with an `EXPLORE_BASELINE_EV` "never idle"
  floor). That per-cycle EV-select over whatever screen is showing is exactly the self-driving shape
  candidate-mining is defined *against*, and it diverges from stop-on-unknown. Recorded here as the
  boundary this concept must not be read as blessing; the runtime fix lives in
  [app-autopilot-model](/architecture/app-autopilot-model.md) and [priority-engine](/engine/priority-engine.md),
  which own that divergence — mining's contribution is to keep its own output a *proposal*, never a tick.

- **The 78-turn auto-haggle misfire is the concrete scar behind the loop STOP-guard.** A verified
  live run let a deterministic resolver keep answering offer prompts far past sense (~78 turns) — the
  archetypal cost of a running behavior that improvised instead of stopping. Mining proposes loops as
  `repeating` macros, so this concept prescribes the depletion→STOP-guard above precisely so a mined
  loop, once approved, cannot reproduce that misfire; the resolver hardening itself is owned by
  [action-safety-guards](/doctrine/action-safety-guards.md) and the auto-haggle concept.

- **Combat is out of mining's reach by construction, and stays there.** Mining ranks by credits and
  turns from ledger rewards; a PvP action carries no such reward shape and is human-gated regardless, so
  the miner neither proposes nor could arm a combat behavior. Any fight math is NPC-only and lives in
  the toll/defense strategy — noted so the boundary is explicit, not assumed.

# Citations

- Reborn vision (fixed constraints): the app plays back only taught screens and stops on the unknown;
  the AI is a retrospective, human-invoked rule author, never a live keystroke; every rule — human- or
  AI-authored — is an inert draft until human-approved; a guard may STOP and escalate instead of firing;
  never fire an unverified/destructive action (start-anchor + send-and-confirm — the −75-alignment
  colonist scar); combat is human-gated, NPC-only math.
- Operator rulings (2026-07-23): candidate-mining and the AI teacher are kept split along the
  LLM-versus-deterministic seam; the deterministic miner's own drafts are a mechanism separate from the
  teacher's on-demand proposals and unaffected by the teacher-only ruling.
- Project canon: the [trace ledger](/engine/trace-ledger.md) (the passive substrate mined here, its
  `{app, human}` actor model and reward schema), the [AI teacher](/engine/ai-teacher.md) (the sibling
  proposer sharing the approval surface), the [rule/macro engine](/architecture/rule-macro-engine.md)
  (where an approved draft becomes a fireable behavior), the [priority engine](/engine/priority-engine.md)
  (the shared cr/turn scorer that orders behaviors), [trade-loops](/strategy/trade-loops.md) (chain
  scoring and depletion policy), [app-autopilot-model](/architecture/app-autopilot-model.md) (the
  run-loop that owns stop-on-unknown and the depletion STOP), and [action-safety-guards](/doctrine/action-safety-guards.md)
  (the start-anchor + send-and-confirm contract a mined draft inherits).
- Reimagined from `knowledge/architecture/autonomy-loop.md` (the session-retro half) — carried forward:
  ledger-mining for recurring profitable decisions worth codifying. Re-rooted: the retro's target is
  recurring profitable input-subsequences, not a live-`ai` slice; the autonomy-ratio gauge that doc
  paired with the retro is deliberately not carried here (it is recast under
  [coverage-metrics](/engine/coverage-metrics.md)).
- Code modules (plain text): `miner.py` (sliding-window grouping, `<NUM>` normalization, cr/turn
  ranking, redaction skip, start-anchor threading, draft proposal), `analyze.py` (session-retro
  slicing and ranking), `ledger.py` (the mined substrate and its reward math), `skills.py` (draft
  write and human promotion), and the Architecture map / Hard rules in `CLAUDE.md` (single-session
  daemon, secrets never touch logs/argv/repo).
