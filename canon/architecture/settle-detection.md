---
type: System
title: Settle Detection & Screen Readiness
description: How the engine decides a rendered screen has stopped changing and is safe to act on, and absorbs known interjections without mistaking them for the novel screens that must escalate to the human.
tags: [architecture, settle, screen-readiness, reliability, escalation]
timestamp: 2026-07-23T19:47:47Z
---

Settle detection is the reliability core of the trainer. Every actor that ever reads or acts on
the game screen — the deterministic **App** autopilot, a **Human** pilot's console, a read-only
**Spectate** client, and the retrospective **AI** teacher reviewing a trace — consumes a *settled*
frame, never a mid-transition one. A settled frame is the atomic unit the rest of the system is
built on: [Screen Understanding](/engine/screen-understanding.md) classifies only settled frames,
the reflex layer fires rules only on settled+classified frames, and
[Control & Escalation](/architecture/control-and-escalation.md) escalates only when a settled frame
matches no known screen. This concept owns the "has the screen stopped moving, and is it what it
appears to be" decision. It does not own classification, rule matching, or the control dual — it is
the gate those layers stand behind.

# The Settled Unit

After input is sent to the game, the engine waits for the screen to *settle*. A frame is declared
settled on the **first** of three conditions, and the winning condition is returned to the caller
as a typed `settled_reason` so no downstream consumer has to re-derive why the wait ended:

- **`prompt`** — a caller-supplied `wait_prompt` regex matches the rendered screen text. This is
  the strongest signal: the screen is not merely quiet, it is quiet *on a specific, named shape*
  the caller was waiting for.
- **`idle`** — no new bytes have arrived for the debounce window (default 350 ms), **and** at least
  one byte has arrived since the send. The second clause is load-bearing: a screen is never called
  settled before the server has said anything at all, so an instantaneous "nothing changed yet"
  can never masquerade as "done."
- **`timeout`** — the overall wait budget (default 8 s) elapsed before either of the above. This is
  a bounded-failure result, not a success: the caller learns the screen never reached a positively
  recognizable rest state.

`settled_reason` travels with the frame all the way to the surfaces (the watch/spectate event
stream and the `do` verb's response both carry it). A `timeout` reason is a first-class "I could
not confirm this screen" signal, not silently swallowed into a pretend-settled frame.

# Why Zero-Reasoning Autopilot Is Possible

The reborn App is deterministic: it plays only taught screens, running a guarded rule → macro
lookup with **no AI reasoning per cycle** (see [Control & Escalation](/architecture/control-and-escalation.md)
and the rule-macro engine). That is only safe because settle detection guarantees the App is always
looking at a *stable, fully-painted* screen when it decides. If the App could act on a
half-transitioned frame it might match the wrong rule, or match a rule that no longer applies once
the paint finishes. Settle detection is therefore the precondition that makes zero-reasoning
autopilot trustworthy: the App never reasons its way through ambiguity because it never acts on an
ambiguous (unsettled) frame in the first place. The chain is strict — **settle → classify → match →
fire**, and every arrow refuses to advance on an unsettled input.

# Invariant: `wait_prompt` Is Case-Sensitive

`wait_prompt` regexes are compiled **without** `re.IGNORECASE`. This is a hard, load-bearing
invariant, not an oversight: a `wait_prompt` that mismatches only on letter case does **not** raise
an error — it silently fails to match and the wait falls through to `timeout`. A caller that writes
`Command \[TL=` where the screen shows `command [tl=` will simply time out with no diagnostic. Every
rule author, macro recorder, and login sub-step that supplies a `wait_prompt` must match the screen
text's exact case. This invariant is stated once here and relied on everywhere; it must never be
"simplified" by adding a case-insensitive flag, because doing so would let a sloppy prompt silently
match the wrong screen — precisely the failure mode the strictness exists to prevent.

Note that *classification* anchors (a separate layer, in
[Screen Understanding](/engine/screen-understanding.md)) are deliberately case-insensitive — that
is a different concern. The case-sensitivity invariant is specific to the caller-supplied
`wait_prompt` settle target.

# Per-Screen Settle Profiles

A single fixed debounce window is wrong for some screens. The trainer's canonical hazard is the
**slow multi-stage animation** — most notably the hub/warp transition, which paints in several
bursts with quiet gaps *between* the bursts. A naive idle-debounce settle can be satisfied by one of
those mid-animation lulls and hand the caller a screen that *looks* finished but is still changing.
This has bitten live pilots repeatedly (a mis-aligned auto-taken-colonist prompt, an
auto-given-away cargo — the send/settle-race scars).

The reborn design treats settle behavior as a **per-screen profile**, not a global constant. A
warp-style screen uses a *warp-aware profile*: after an apparent settle, it re-checks that the
screen is **still** stable one more quiet beat later, and it treats an unmatched mid-animation lull
as a lull to keep waiting through — not as proof the screen is done — re-polling against the
remaining budget until either the true target shape arrives or the whole budget runs out. Two
distinct confirmation modes exist:

- **Positive-shape confirmation** — when the caller can name the target screen shape, the settled
  frame must *positively match* that shape, never idle-only. An unmatched idle is discarded and the
  wait resumes; only a genuine match (or budget exhaustion) ends the wait. After a match, one more
  brief stability beat re-checks the shape is still present, rejecting a screen that flashed the
  match for a single frame and moved on.
- **Stable-idle confirmation** — when the caller has no nameable target (a replayed macro step or a
  login sub-step often does not), confirmation falls back to a *genuinely stable* idle: the screen
  went quiet and **stayed** quiet across one further stability beat. This is a strictly weaker
  guarantee — it proves a screen arrived and stayed, not *which* screen — so any caller that can
  name a target shape should always prefer positive-shape confirmation.

Positive-shape callers also choose the narrowest honest match provenance. A
whole-screen match is appropriate only when the target may span rows.
`prompt_line` scopes to the last non-empty cropped row. A dialogue cascade may
instead require `cursor_line`: the row holding the live terminal cursor. TWGS
can leave an older `Command` row painted *below* the second or third commodity
question, so “last painted row” and “current input prompt” are not equivalent.
Money-path cascades use cursor-line scope and halt if that provenance is
unavailable; stale text elsewhere on the grid never proves the next answer is
safe.

A related send-side rule belongs to the same anti-race discipline: the caller decides **per send**
whether a trailing Enter is appended, rather than a blanket default. A menu-style single-key
selection sent with an unwanted trailing CRLF can have that Enter consumed by the server as a
blank/default-accept on the *next* prompt, before the caller's real answer is ever sent — and bytes
already on the wire cannot be un-sent. Eliminating the stray Enter at the source is the live-proven
fix.

# Interjection Registry: What Makes Escalate-on-Unknown Trustworthy

The game injects **unsolicited output** that is not a novel screen and must not be treated as one:
the `[Pause]`/`-- More --` pager, the periodic inactivity warning, the "Show today's log?" prompt,
and similar known interjections. These are *nuisances* with known, safe, standing responses (dismiss
the pager, decline the log, answer the keepalive). If the App escalated to the Human every time one
appeared, escalate-on-unknown would be too noisy to trust — the Human would be interrupted by
routine chrome and would learn to ignore the STOP banner, defeating its purpose.

The reborn design maintains a first-class **interjection registry**: an enumerated set of known
unsolicited-output shapes, each paired with a standing, safe auto-handling response. A settled
frame matching a registry entry is auto-handled and the underlying flow continues — the App does not
escalate, and the interjection never counts as an unknown screen.

The registry's boundary is exactly what makes the whole control model safe:

- **A registered interjection is absorbed** — auto-handled, silently, because its response is
  known-safe and standing.
- **A genuinely novel screen is surfaced, never swallowed** — anything *not* in the registry and
  *not* a taught screen is an unknown, and an unknown always STOPs the App and hands the keyboard to
  the Human (see [Control & Escalation](/architecture/control-and-escalation.md)). The registry is a
  closed allow-list of nuisances, not a catch-all "handle whatever we don't recognize."

This asymmetry — a small, explicit allow-list of absorbable interjections against an
escalate-everything-else default — is precisely what lets the Human trust that a STOP banner means
*a real unknown*, not routine chrome. The registry must therefore stay conservative: adding a shape
to it is a decision to *never* show that shape to the Human, so only genuinely safe, standing-response
interjections belong there. When in doubt, a shape is surfaced, not registered.

# Settle-Edge → Push: The Liveness Signal

Settle detection also drives the **liveness stream** behind `tw watch` and `tw spectate`. A
background watcher continuously observes the rendered screen and emits a *settle edge*: a moment
where the screen has both (a) gone idle past the debounce window and (b) actually changed since the
last edge it announced. Each edge is broadcast — carrying the same settled-frame shape and a
`settled_reason` of `idle` — to every currently-subscribed observer, so a spectator sees the game
advance in the same settled units the App acts on.

This push stream is deliberately **separate** from the synchronous per-send settle wait. The
synchronous wait answers "has *this specific send* settled yet?" for one `do`/`read` call; the
push stream answers "what is the game doing *right now*?", continuously, for however many passive
observers are attached. Both read the same session screen through the same lock and otherwise do
not interact. A new subscriber is seeded with the current settled screen as its first event, so a
spectator tuning in mid-session sees state immediately rather than waiting for the next change.

Critically, the push stream is **observation, not intervention**: it streams every settle edge
as-is and performs no auto-handling of its own. Interjection absorption (the registry above) is a
*control-side* responsibility of whoever is driving — it is not the watch stream's job. A spectator
watching the App drive sees the interjection appear and the App's auto-response, both as settle
edges; the stream never hides or answers anything on the observer's behalf.

# Schema

The settle contract, as consumed by callers:

| Element | Meaning |
|---|---|
| `settled_reason: prompt` | A caller-named `wait_prompt` regex matched the settled screen — strongest confirmation. |
| `settled_reason: idle` | Screen quiet for the debounce window with ≥1 byte since the send — quiet, but shape not asserted. |
| `settled_reason: timeout` | Wait budget elapsed with no positive settle — a bounded "could not confirm," not a success. |
| `wait_prompt` | Caller-supplied target regex. **Case-sensitive** — a case mismatch silently times out. |
| debounce window | Quiet interval that defines "idle" (default 350 ms); part of a screen's settle profile. |
| wait budget | Overall timeout ceiling (default 8 s) bounding the whole settle wait. |
| positive-shape confirmation | Settled frame must *match* a named shape, and still match one stability beat later. |
| stable-idle confirmation | Fallback when no shape is nameable: quiet, and *stays* quiet across one more beat. |
| interjection registry | Closed allow-list of known unsolicited-output shapes with standing safe responses; everything else escalates. |
| settle edge | A push event: screen idle past debounce **and** changed since the last announced edge. |

# Examples

A warp transition settling correctly under a warp-aware profile:

```
1. App sends the move. The hub/warp screen begins painting in bursts.
2. A mid-animation lull satisfies the raw debounce window. A naive settle would stop here —
   the warp-aware profile does NOT: the screen isn't the confirmed target shape yet.
3. Painting resumes; more bursts arrive. The profile keeps re-polling against the remaining
   budget rather than declaring the mid-animation lull "settled."
4. The final Sector screen paints and goes quiet. It matches the target shape AND is still
   present one stability beat later. Settle returns reason=prompt. Only now does the App act.
```

A `[Pause]` interjection absorbed, versus a novel screen surfaced:

```
1. App is driving. A `[Pause]` pager appears at the bottom of an otherwise-known screen.
2. The settled frame matches the interjection registry. The App auto-dismisses the pager and
   the flow continues. No escalation — routine chrome, standing safe response.
3. Later, a settled frame matches NO taught rule AND NO registry interjection.
4. This is a genuine unknown. The App STOPs and hands the keyboard to the Human with a STOP
   banner. The registry's conservatism is why this banner is trustworthy: it never fires for
   a `[Pause]`, only for a real unknown.
```

# Code Divergence

**(1) The interjection registry is not yet a first-class subsystem.** The reborn design specifies a
single enumerated registry of unsolicited-output shapes paired with standing safe responses. In the
current code, interjection *classification* exists (`classify.py` anchors `pause_key` for
`[Pause]`/`-- More --`/`press … key`) but auto-handling is **scattered across driving callers**
rather than centralized — e.g. the AUTO-LOOP driver clears a mid-run pager itself, and
`watch.py` explicitly disclaims any auto-handling ("Nuisance auto-handling … is explicitly NOT this
module's job — it streams every settle-edge as-is"). There is no single registry module enumerating
`[Pause]`, the inactivity warning, and "Show today's log?" with their responses. The canon
prescribes consolidating these into one first-class registry so the "absorbed vs. surfaced"
boundary is defined in exactly one place; recorded here as a divergence, not reconciled by this
concept.

**(2) Per-screen settle profiles are ad-hoc caller flags, not a declarative screen-keyed table.**
The warp-aware behavior specified above exists in the code, but as **per-call parameters** on
`settle.send_and_confirm()` — a caller passes `confirm_prompt` (positive-shape mode),
`confirm_prompt=None` (stable-idle mode), and `retry_unstable_idle=True` (the warp/explore
"keep polling through an unstable idle" behavior). There is no screen-keyed *profile registry* that
maps a screen class (e.g. "warp/hub animation") to its settle parameters automatically; each caller
must know to pass the right flags. The canon prescribes promoting these into named, screen-associated
settle profiles so warp-awareness is selected by *what screen it is*, not by each caller
remembering the correct flags. Recorded as a divergence; the code fix is a separate future work
order.

# Citations

[1] twclient/settle.py (`wait_for_settle`, `wait_until_settled`, `send_and_confirm`; case-sensitive
    `wait_prompt`; send/settle-race and warp-animation handling)
[2] twclient/session.py (the live settle-detection protocol surface: `rx_count`, `last_rx`,
    `clock`, `sleep`, `render_text`, `wait_settle`)
[3] twclient/watch.py (`WatchHub` settle-edge push stream; explicit no-auto-handling boundary)
[4] twclient/terminal.py (pyte-backed render the settle wait polls)
[5] twclient/classify.py (`pause_key` and other gate anchors — interjection classification today)
[6] Historical settle design (retired root `DESIGN.md` §6, now owned here); DESIGN-v2.md §8 (send/settle race, B4/B5 — internal planning history)
[7] [/research/tw2002-screen-patterns.md](/research/tw2002-screen-patterns.md) (P-SETTLE-LINE · P-SUPPRESS — prompt-line scope + suppressed sub-prompts)
[8] [/research/archive-port-patterns.md](/research/archive-port-patterns.md) AP-02 (send_and_confirm detailed algorithm, stale pre-send guard, stability re-check, retry_unstable_idle, wait_until_settled pre-read gate)
