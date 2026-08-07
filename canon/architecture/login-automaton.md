---
type: System
title: Login Automaton
description: The classification-driven expect/respond automaton that drives a cold socket through the BBS/TWGS interstitials to the in-game Command prompt, branching NEW-vs-RETURNING and reading the secure credential store.
tags: [architecture, login, automaton, credentials, reconnect]
timestamp: 2026-07-23T19:47:47Z
---

The Login Automaton is the piece of machinery that takes a freshly-opened, silent telnet socket
and drives it — one settled screen at a time — all the way to the in-game `Command [TL=…]` prompt,
where live control can begin. It is **control-neutral**: it runs *before* the App/Human control
dual exists, because there is no game to pilot until a character is logged in. Nothing in
[the Control & Escalation model](/architecture/control-and-escalation.md) is in force yet — there
is no keyboard to hand to the human, no rule set to match against. This concept specifies how the
automaton recognizes each login screen, what it sends, how it branches, and the one credential fact
it needs (where the password comes from); the full secret-handling discipline lives in
[Secrets & Credentials](/doctrine/secrets-and-credentials.md) and is cross-linked, never restated.

# The Automaton Is Reactive, Not a Script

The automaton is deliberately **not** a fixed step sequence. Every iteration re-renders the current
settled screen, classifies it (via [Screen Understanding](/engine/screen-understanding.md)), and
dispatches on *what the screen currently is* — never on "what step number we think we're on." This
is the load-bearing design choice: the real TWGS/BBS login flow interleaves nuisance interstitials
(a `[Pause]` "press any key", an inactivity warning, "Show today's log?", "You have been on today",
"Do you wish to clear some avoids?") at points that vary run to run. Because dispatch is keyed on
the present screen, a re-ordered or unexpectedly-inserted interstitial can never desync the
automaton — it simply handles whatever is in front of it and re-classifies on the next pass.

Two direct consequences fall out of this for free:

- **Idempotent resume.** Pointing the automaton at a screen that is already mid-flow just resumes
  the unmet suffix — the same run logic serves a cold start and a "finish what's left" call with no
  special casing. This is what makes an `ensure`-style call safe to issue against an unknown-state
  session.
- **Replayable by the guardian.** The same self-contained drive sequence the automaton runs on a
  cold connect is exactly what [Resilience & Reconnect](/architecture/resilience-and-reconnect.md)
  replays after a dropped socket — reconnect, then re-drive to the Command prompt, then verify the
  resumed screen before returning control. The automaton owns "get logged in"; the guardian owns
  "notice the drop and ask for it again."

# From Cold Socket to Command Prompt

The canonical TWGS-direct flow the automaton drives, expressed as recognition→response (order is
illustrative only — the automaton keys on the screen, not the row number):

| Screen it recognizes | What it sends |
|---|---|
| Outer BBS name prompt ("… ENTER for none") | blank (Enter) |
| Server door-select menu ("Select a game :") | the profile's game letter |
| Module-entry menu ("T - Play Trade Wars 2002") | `T` |
| "Use ANSI graphics?" | `Y` |
| "Show today's log?" | `N` |
| Character-handle prompt ("What is your name?") | the profile handle |
| **NEW** branch — "start a new character?" | `Y` → (registration, below) |
| **RETURNING** branch — password gate | the saved password (once) |
| `Command [TL=…]` | *(target reached — return)* |

Nuisance interstitials are matched *ahead of* the main dispatch, on raw screen text, so they can
interrupt any branch without desyncing it: `pause_key` → blank Enter, "Show today's log?" → `N`,
inactivity warning → harmless blank Enter, "you have been on today" → blank Enter, "clear some
avoids?" → `N` by default (keeping the avoid list — clearing it would discard navigation memory;
opt in per-profile only).

**Menu selections send no trailing newline.** The server-level game-select prompt is answered with
a bare keystroke and no CRLF — a trailing newline there produces a phantom blank line that can
confuse settle detection.

# NEW vs RETURNING

The branch point is structural, not guessed. The character-handle prompt leads to exactly one of
two gates:

- **RETURNING** — the flow reaches a **password gate** without ever having shown a "start a new
  character?" screen. That means the handle was found in the player database. The automaton reads
  the saved password from the store (below) and sends it **once**. A wrong or stale saved password
  is a **hard, fail-loud failure** — the automaton never guesses, never brute-forces, and never
  retries a credential past a small fixed ceiling.
- **NEW** — a "start a new character?" screen *does* appear (the handle was not in the database).
  This is gated behind an explicit per-profile **opt-in** (`allow_register`, default off): on a
  profile that has not opted in, the automaton **refuses before sending the keystroke that begins
  registration**, exactly as it refuses any consequential act it was not authorized to take.
  Auto-creating a character on a live server is a policy decision, not a mechanical one.

When registration *is* permitted, the automaton generates a fresh password and **saves it
immediately** — before the first send — so the new character is durably recoverable even if a later
step fails. It then plays the cosmetic sub-steps from **profile-supplied pools**: a handle, a ship
name, and a home-planet name (any field the operator pinned always wins; unpinned fields draw from
a name bank, redrawing on a handle collision with an existing character). Every auto-answered
registration prompt is restricted to purely **cosmetic / non-committal** confirmations with no
gameplay effect — the automaton will never blind-answer a prompt that changes game state (the
scar-tissue rule from the auto-defaulted-colonist-alignment incident: a gameplay-affecting choice
is never guessed). An unrecognized registration prompt falls through to the same fail-loud path as
any other unknown screen.

# The Credential It Reads

The automaton needs exactly one secret — the password — and it obtains it through an injected
resolver, never by reaching into a file itself. The resolver precedence is:

1. **Environment first** — `TW2002_PASSWORD_<PROFILE>` (profile name upper-cased, non-alnum → `_`).
   This lets an operator or CI supply a throwaway credential without ever writing it to disk.
2. **Else the chmod-600 secrets store** — the sole on-disk home for passwords, created and
   re-asserted at mode `600` on every write.

A profile's **non-secret shape** (host, port, game letter, handle, cosmetic overrides) lives in a
separate, freely-readable profiles file; the password lives **only** in the secrets store or the
environment. This metadata-vs-secret split, the atomic-write and permission discipline, and the
"absent password is a legitimate `None`, not an error" contract are specified in full by
[Secrets & Credentials](/doctrine/secrets-and-credentials.md) — this concept depends on them but
does not re-specify them. Which profile is selected, and how a bare host/port profile resolves, is
owned by [Entry & Profile Selection](/surfaces/entry-and-profile-selection.md).

# The Redaction Invariant

The password **never** touches this automaton's return values, its exceptions, its trace, or any
log line. Every send of it goes through the session's secret-send path, which routes to the
transcript logger's redacted write — the same redaction path proven for interactive secret entry.
Secrets never reach logs, argv, shell history, or the repo; this is a hard, cross-cutting invariant
stated once here and owned in full by [Secrets & Credentials](/doctrine/secrets-and-credentials.md).

# Fail-Loud on the Unknown

The automaton embodies the same **never-guess** spine as the rest of the trainer: a screen it does
not recognize is never answered with a default keystroke. If an unrecognized screen (or a send that
cannot be positively confirmed) repeats past a small stagnation budget, or the overall step budget
is exhausted, the automaton raises a **loud, typed failure** rather than sending a keystroke it
isn't sure about. Every send is positively confirmed (send-and-confirm, not a bare fire-and-idle),
so the automaton never treats a screen that only *transiently* looked settled mid-transition as
proof its last answer landed; a genuinely slow multi-part redraw (an ANSI banner finishing) is
tolerated within the same budget, while a persistently-failing confirm still fails loudly instead
of spinning forever.

The **single-connection** rule holds throughout: one daemon owns the one telnet connection, guarded
by a pidfile; the automaton drives that single connection and nothing else opens a second.

# Schema

| Element | Contract |
|---|---|
| Input | a live session sitting on some login-flow screen (cold or mid-flow); a profile; injected `get_password` / `save_password`. |
| Output | `(final_classification, steps_taken)` once `Command [TL=…]` is reached — never returns without reaching the target or raising. |
| Dispatch key | the **current** settled screen's classification + prompt line, re-evaluated every iteration. |
| NEW gate | explicit per-profile opt-in; refuse before the first registration keystroke otherwise. |
| RETURNING gate | saved password sent once; wrong/stale/missing → fail loud, never retried past a fixed ceiling. |
| Password source | env `TW2002_PASSWORD_<PROFILE>` first, else chmod-600 secrets store. |
| Redaction | every password send routes through the redacted-send path; password never in return/exception/trace/log. |
| Failure | typed, loud error on repeated-unknown / unconfirmed-send / exhausted-steps / bad-credential. |
| Reuse | the same drive sequence is replayed by the reconnect guardian post-drop. |

# Examples

A RETURNING cold login, end to end:

```
1. Socket opens silent. Automaton renders the first settled screen, classifies it.
2. Door-select menu → sends the profile's game letter (no trailing newline).
3. Module-entry menu → "T".  "Use ANSI graphics?" → "Y".  "Show today's log?" → "N".
4. Handle prompt → the profile handle.
5. A password gate appears with no "new character?" screen ever having shown → RETURNING.
   Automaton reads the saved password (env, else chmod-600 store) and sends it once, redacted.
6. "You have been on today" interstitial → blank Enter.  Command [TL=…] → target reached, return.
```

A permitted NEW registration:

```
1. …handle prompt → the (possibly name-bank-drawn) handle.
2. "start a new character?" appears. Profile has allow_register = true → proceed.
   Automaton generates a fresh password and SAVES it immediately, before sending anything.
3. Password create/verify prompts → the same generated value, resent identically through any
   "didn't match" re-ask, always redacted.
4. Cosmetic sub-steps: BBS-name choice → "B"; ship name → profile ship pool; confirm → "Y";
   home-planet name → profile planet pool; planet command → "Q".
5. Command [TL=…] → target reached. The character is durably recoverable from step 2's save.
```

A refusal (fail-loud, never a guess):

```
1. …handle prompt → handle.
2. "start a new character?" appears, but the profile did NOT opt into registration.
3. Automaton raises a typed "registration_not_permitted" error WITHOUT sending the "Y".
   No character is created; the caller decides what to do.
```

# Code Divergence

**The login automaton is authored-in-code, not a set of taught rules — by design, and it is the one
sanctioned exception to "the App plays only taught screens."** In the reborn model the App drives
by matching *human-taught, human-approved* guarded rules and STOPs (hands the keyboard to the
human) on anything unrecognized. The login automaton (`tw2002_aiclient/session/login.py`) is instead a built-in,
hard-coded expect/respond table that drives deterministically before any control dual or rule set
exists. This is consistent with the vision's disposition for this concept (control-neutral; it
precedes the App/Human dual because no game control exists until logged in), and it preserves the
same never-guess spine — but it is recorded here so the login table is not mistaken for a taught
behavior in the reflex rule-macro layer. It sits *outside* that layer intentionally.

**Login-time "escalate-on-unknown" resolves to a fail-loud error, not a live keyboard handoff.**
In-game, an unrecognized screen means App→Human: STOP and hand over the keyboard. Pre-login there
is no human-pilot surface to hand to, so the automaton's equivalent of that STOP is a typed
`LoginError` returned to the calling surface (`ensure`/guardian), which then decides. The intent —
never send a keystroke you aren't sure about — is identical; only the recovery target differs
because the control dual does not exist yet. Noted so the pre-Command recovery path is explicit
rather than assumed to mirror in-game escalation.

**The next-prompt confirmation hint is currently always unset.** Because every step re-classifies
the *current* screen from scratch (the reactive design above), the automaton pins no explicit
next-prompt regex and leans on send-and-confirm's idle+stability fallback instead. This is not a
defect — but note that wherever a `wait_prompt`/confirm regex *is* supplied anywhere in this
system, it is **case-sensitive** (there is no `re.IGNORECASE` on that path): a case-mismatched
prompt regex silently times out rather than erroring. Any future decision to pin a login-step hint
must respect that invariant exactly.

# Citations

[1] `tw2002_aiclient/session/login.py` (the automaton: `run_login`, `_decide`, NEW/RETURNING branch, name-bank rider; ported from archive `twclient/login.py`)
[2] `tw2002_aiclient/session/credentials.py` (env-first `get_password`, chmod-600 secrets store, `allow_register` gate)
[3] `tw2002_aiclient/session/classify.py` (`classify_screen`, gate-vs-content anchors, game-select/interstitial recognition)
[4] DESIGN-v2.md §B1/B2/B3 (login automaton, secure store, NEW-vs-RETURNING branch — internal planning history)
[5] canon/log.md 2026-07-23 (reborn control-neutrality disposition for this concept)
[6] canon/research/archive-port-patterns.md AP-03 (reactive loop pseudocode, nuisance table,
    stagnant_rounds tracking, game_select_answered once-per-connection guard)
