---
type: System
title: The Trace Ledger — Semantic Record & Actor Attribution
description: The append-only, per-dispatch semantic record of what happened, who sent it, and what it earned — the single passive substrate that mining, the teacher, and the human read, and that never itself decides anything.
tags: [ledger, actor-attribution, observability, retro, provenance, passive-substrate, redaction, prescriptive]
timestamp: 2026-07-23T20:01:51Z
---

The trace ledger is the trainer's memory of *what happened*. Every time a live keystroke is
dispatched through the one game connection, a single row is appended describing the screen that was
answered, the input that answered it, who sent it, and what changed as a result. Nothing about the
ledger drives play. It is written by the dispatch path and **read** — by candidate-mining looking
for patterns worth teaching, by the AI teacher reconstructing a moment worth codifying, by the
human scanning a trail of what their session did. A store that is read to *drive* a live keystroke
would violate the trainer's spine; the ledger is deliberately the opposite of that — a passive
record, never a decision-maker. This concept is prescriptive: it specifies the row schema, the
actor-attribution invariant, and the four-tier observability model the reborn trainer targets, and
records where the current code still carries the pre-reborn shape.

# Schema

## The ledger row

Every `do`/`send` dispatch that reaches the daemon's choke-point appends exactly one row to a
single append-only JSONL sink. The semantic shape of a row:

| Field | Meaning |
|---|---|
| `ts` | UTC timestamp of the dispatch (real clock, ISO-8601). |
| `prompt` | The game's actual question this input answered — the last non-blank line of the pre-send screen, e.g. `Your offer [158]?`. Lets a reader tell *what* an input was replying to, not merely that something was typed. Redacted if it is a password prompt. |
| `pre_state` | Best-effort structured game-state before the send (credits, sector, turns, empty cargo holds, …), read read-only from the state parser. |
| `input` | The keystroke(s) sent. `<redacted>` for a secret (password) send — never the literal credential. |
| `post_state` | The same structured state read after the screen settled. |
| `settled_class` | The classification of the settled screen the send produced. |
| `screen_delta` | A compact human-readable summary of what changed on screen — a line-level diff (`+a/-b/~c lines`), not a full grid dump, so a row stays greppable by eye. (Code field: `screen_delta_summary`.) |
| `reward` | The outcome delta: `{d_credits, d_turns, d_cargo}`, each computed as post − pre and present only when both sides carried the underlying field. `d_turns` is normally ≤ 0 (turns are spent); a pattern's turn *cost* is `-d_turns`. |

Two omission conventions are load-bearing and shared across the row: **a missing key means
"unknown," never zero.** A `reward` field is absent when either state lacked its input; an older row
written before a field existed simply lacks that key, and every read site treats absence as
unknown. This is what lets the sink grow forever without in-place migration — old rows stay fully
readable beside new ones.

## Actor attribution — the invariant

Every row carries who sent the keystroke, and this attribution is the load-bearing part of the
reborn record. The trainer has exactly **two live senders of keystrokes: `app` and `human`.**

- **`app`** — a deterministic, no-LLM engine send: a taught macro replaying, a built-in guarded
  rule firing (auto-haggle), a repeating loop stepping. Zero AI reasoning happened at send time;
  the app is playing back only what it was taught, and it stops on anything it doesn't recognize.
- **`human`** — a keystroke the operator typed directly in an interactive (`tw attach`) session.
  The human is the sovereign pilot and the escalation target; a human send is the operator steering.

**There is no live `ai` sender.** The AI is a *rule author*, never a keystroke. It reads a screen or
a session retrospectively, on human demand, and proposes a guarded rule draft for human approval;
an approved rule becomes a deterministic behavior the *app* later plays. AI provenance is therefore
a property of a *rule's authorship*, not of any ledger row's live send — the ledger's `actor` axis
records who pressed a key, and the answer is only ever `app` or `human`.

Alongside `actor`, every row carries a **`session_id`**: it correlates a run of rows to one
continuous play session (and to that session's own transcript and frame logs), making "a session" a
queryable unit rather than an arbitrary slice of one unbroken stream. An optional **`intent`** may
carry a short authored rationale for a send ("selling organics, port buys above average"), which is
what makes a recurring decision recognizable as a pattern worth codifying — but it is optional and
never required for a row to be valid.

> **Invariant:** live keystroke senders are `{app, human}` only. `session_id` is present on every
> row. The AI is an author of rules, never a live sender — its contribution is measured as rules
> authored/approved, a provenance axis entirely separate from the `actor` field. This sits beside
> the trainer's other spine invariants (per-world keying; secrets never touch logs/argv/repo).

# Four tiers of observability

The ledger is one of four distinct records the trainer keeps, each at a different altitude and for a
different reader. They are not redundant — each answers a question the others cannot, and knowing
which tier to reach for is part of the design.

| Tier | Record | Shape & lifetime | Answers |
|---|---|---|---|
| 1 — **Wire log** | Full session transcript (`logs/session-<id>.log`, `logging_util.py`) | Append-only raw RX/TX bytes, per session, human-readable. | "What bytes actually crossed the socket?" — the ground truth for debugging emulation, negotiation, or a garbled screen. |
| 2 — **Ledger** | Semantic per-dispatch rows (`state/ledger.jsonl`, `ledger.py`) | Append-only JSONL, one row per settled `do`/`send`, small enough to grep. | "What decision was made, by whom, answering what, and what did it earn?" — the learning + attribution substrate. |
| 3 — **History ring** | In-memory recent-event ring (`session.py`, cap ~200) | Ephemeral, RAM-only, evicts oldest; dies with the daemon. | "What just happened, right now?" — the live `tw history` view; never durable, never mined. |
| 4 — **Frame capture** | Full-grid settled frames (`state/frames/<session_id>.jsonl`, `frame_recorder.py` / `tw frames`) | Append-only NDJSON, one object per settled screen, carrying the entire 80×25 grid (`screen_raw`) plus cropped view, cursor, classification, and the input that produced it. | "What did the *whole screen* look like at that moment?" — post-mortem replay and greppable reconstruction, even when spectate clipped a row or watch coalesced intermediate screens. Read path is pure filesystem: no daemon needed for a closed session. |

The ledger (tier 2) is what learning reads; the frame capture (tier 4) is what a human or the
teacher reads to reconstruct an escalation moment in full fidelity, because the ledger's `screen_delta`
is a summary, not the pixels. The two are complementary: the ledger says *a decision earned +230cr
here*; the frames say *and here is exactly the screen that decision faced*. Both are keyed by
`session_id` so a retro can pivot between them.

# Redaction discipline

No secret ever reaches any tier. Password entry is dispatched with a `secret` flag, and every sink
honors it independently:

- The **wire log** records only that a redacted send happened, via `log_redacted()` — no bytes, and
  **no byte count** either, since length itself would leak.
- The **ledger** stores `input: "<redacted>"` and, belt-and-suspenders, redacts the `prompt` too —
  both when the prompt line matches the password anchor *and* unconditionally on a `secret`
  dispatch, so a password can't slip through on an oddly-shaped prompt screen.
- The **frame capture** redacts its `sent_input` the same way, on either the `secret` flag or a
  password-anchored prompt line.

This is one decision — "is this send secret?" — read by all sinks, never re-derived per sink. A
password never touches a log, argv, shell history, or the repo; the ledger and frames are just more
surfaces the same hard rule covers.

# Passive substrate — it never decides

The ledger is written by the dispatch path and read by four consumers, none of which is a live
driver:

- **Candidate-mining** reads ledger slices to find recurring, profitable input-subsequences and
  proposes them as *draft* macros/loops for human approval (see
  [candidate-mining](/engine/candidate-mining.md)).
- **The AI teacher** reads a session's rows (and the correlated frames) to reconstruct a moment and
  propose a *draft* guarded rule — retrospectively, on human demand (see
  [ai-teacher](/engine/ai-teacher.md)).
- **The human** reads the trail directly (below).
- **Coverage metrics** count rows by `actor` to gauge how much of the *known* the taught app is
  handling versus how often it escalated (see [coverage-metrics](/engine/coverage-metrics.md)).

A store that read *itself* to choose the next live keystroke would be a self-driving loop — exactly
the shape the reborn trainer forbids. The ledger is read to *teach* and to *measure*, never to act.
The classic anti-pattern it must not become: a live scorer picking an action per cycle from its own
history. It records; the human (and the human-approved rules) decide.

# Human-readable trace render

`tw log` / `tw trail` renders the ledger directly (pure filesystem read, no daemon round trip) as a
one-line-per-row trail: **question → keystroke → result.**

```
07:08:45 port_trade  Q ▸ "…your offer [158]?"  ⌨ ▸ «158»  → +230cr (96,553→96,783)
```

Two rendering rules are deliberate, not cosmetic:

- **Every keystroke is visible.** A blank/default-accept send (recorded as `input: ""`) renders as
  `«⏎ Enter (default)»`, a backspace as `«⌫»`, other control bytes in caret notation (`«^]»`) — so a
  default-accept is never indistinguishable from "nothing happened." The highlighted token is always
  a non-empty `«…»`.
- **Redaction survives rendering.** A redacted input renders as `«<redacted>»`; the credential's
  context never reappears in the trail.

The result portion prefers the credits delta with its absolute pre→post reading (the most scannable
signal), falling back to turns, then cargo, then the raw screen-delta summary, then "no change."

# Examples

```
Ledger rows (illustrative — reborn actor values):
{ts: …, actor: "app",   session_id: "s-42", prompt: "Your offer [158]?", input: "158", reward: {d_credits: 230}}
{ts: …, actor: "app",   session_id: "s-42", prompt: "How many holds?",   input: "50",  reward: {d_credits: 0, d_turns: 0}}
{ts: …, actor: "human", session_id: "s-42", prompt: "Command [TL=…]:",   input: "M4223"}
```

- The two `app` rows are a taught macro replaying deterministically — no AI at send time.
- The `human` row is the operator taking the keyboard (`tw attach`).
- A retro on `s-42` slices by `session_id`, and — because rows carry `actor` — can separate what the
  taught app handled from where the human had to step in, feeding both candidate-mining and coverage
  metrics. To reconstruct the exact screen the macro faced, the same `session_id` indexes into the
  tier-4 frames.

# Code divergence

The reborn actor model above prescribes `{app, human}` live senders with the AI as author-only. The
current code still carries the **pre-reborn three-value enum and a live `ai` default**:

- **`ledger.py`'s `record_do()` declares `actor` as one of `{"ai", "trainer", "human"}` and defaults
  it to `"ai"`.** The default `"ai"` is applied to the direct `do`/`send` dispatch path in
  `protocol.py` — i.e. the code treats an LLM-decided send as a *live* `ai` actor value. Under the
  reborn vision there is **no live `ai` sender**: that path is a deterministic app playback or a
  human keystroke, and AI is a rule author whose contribution is not a ledger `actor` value at all.
  The mapping the code must move to: **`trainer` → `app`** (a deterministic no-LLM engine send), the
  default becomes `app` (or is made explicit per call site), and the `ai` live value is **retired**
  from the enum. `human` is already correct. Docs win: `{app, human}` is the target; the code's
  `{ai, trainer, human}` with an `ai` default is the divergence to close. (Old rows already written
  with `actor: "ai"`/`"trainer"` are not migrated in place — the "missing/legacy value = read as
  best-effort" convention keeps them readable; a retro pass should map a legacy `trainer` to `app`
  and treat a legacy `ai` row as authored-decision provenance, not a live-sender count.)

- **The ledger is a single global sink (`state/ledger.jsonl`), not per-world.** Rows carry
  `session_id` (so a retro can slice by session) but not a world slug, so a clean per-world slice
  requires correlating sessions to worlds out of band. The per-world keying invariant
  (see [world-identity](/engine/world-identity.md)) prescribes a world-scoped view; whether that is
  a per-world ledger path or a world-stamped row that mining filters is an implementation choice this
  concept and candidate-mining should settle. Recorded here as a keying divergence, not a defect in
  the row shape itself.

- **The `intent`/`interrupted_by_human` provenance carried, not yet consumed.** `record_do()` also
  writes an optional `intent` and an `interrupted_by_human` flag (set when a `tw attach` seized the
  control lock mid-dispatch, corrupting that row's action→outcome mapping). The flag's intended
  consumer — a learning-loop pass that must *skip* a corrupted row rather than trust it — is not yet
  live. The field is correct and additive; the divergence is only that its guard is written but not
  yet read.

# Citations

- Reborn vision (fixed constraints): the human is the sovereign pilot and escalation target; the app
  plays back only taught screens and stops on the unknown; the AI is a retrospective, human-invoked
  rule author and never a live keystroke; knowledge stores are read by guards/teacher/human, never
  self-driving. Live keystroke senders are `{app, human}` only.
- Project canon — the North Star three-actor model (see [north-star](/architecture/north-star.md))
  and the Hard Rules (secrets never touch logs/argv/repo; single-session daemon) this record's
  redaction and attribution invariants sit beside.
- Session engine — the dispatch choke-point every row is appended from
  (see [session-engine](/architecture/session-engine.md)).
- Internal design history — the ledger substrate (DESIGN-v2 §3 item 11a, the `tw log`/`tw trail`
  §10 human-readable trail, the WO-FRAMES-0 full-grid frame tier), and the TW-05 actor-attribution
  fields reimagined here from `knowledge/architecture/autonomy-loop.md` (the autonomy-ratio gauge
  that doc paired with attribution is deliberately *not* carried here — it is recast under
  [coverage-metrics](/engine/coverage-metrics.md); this concept keeps attribution as pure
  provenance).
- Code modules (plain-text): `ledger.py` (row schema, redaction, trail render), `frame_recorder.py`
  (tier-4 full-grid frames), `logging_util.py` (tier-1 wire log + `log_redacted()`), `session.py`
  (tier-3 in-memory history ring, the shared secret-decision fields).
