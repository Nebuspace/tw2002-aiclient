---
type: System
title: Resilience & Reconnect
description: The connection-level supervisor that survives a dropped socket via reconnect plus login-replay, and a conservative idle-keepalive that stays OFF on every screen but the single safest one — with a hard rule that a post-resume unknown screen escalates to the human rather than being recovered by a guess.
tags: [architecture, resilience, reconnect, keepalive, safety, human-in-the-loop]
timestamp: 2026-07-23T19:47:47Z
---

The one telnet connection this client owns is mortal: servers kick idle traders, networks blip,
TWGS drops a session after its inactivity countdown expires. **Resilience & Reconnect** is the
background supervisor that keeps the session alive across those events without asking the driving
surface — App or Human — to notice, and without ever turning a recovery into an unsupervised guess.
It has exactly two jobs: **reconnect + login-replay** when the socket has already dropped, and a
**conservative idle-keepalive** that prevents the drop in the first place. Both are safety-bounded,
and both defer to the control model's spine — the human is the sovereign pilot and the escalation
target (see [the North Star](/architecture/north-star.md) and
[Control & Escalation](/architecture/control-and-escalation.md)).

The supervisor is the `SessionGuardian`: a single daemon thread that polls session health every few
seconds. Reconnect and keepalive are two facets of the same "is the session healthy?" poll, so they
share one thread rather than running two redundant pollers. It never drives gameplay, never authors
a rule, and never reasons about the game — it is pure connection plumbing plus one narrowly-scoped
liveness nudge.

# Drop Detection & Reconnect

Each poll tick asks the transport a single question: is the socket still connected? The
[Session Engine](/architecture/session-engine.md)'s reader thread flips a connection flag to false
the moment `recv()` returns empty or errors, so drop detection is a flag read, not a heuristic. On a
detected drop the supervisor attempts to **reconnect the same session** — reusing the one
project-rooted daemon and its pidfile, never spawning a second connection (the single-connection
invariant holds through recovery: reconnect re-opens the socket under the existing daemon, it does
not fork a new one).

Reconnect is **conditional on prior successful login**. The supervisor only replays a login it has
already seen succeed once — a profile recorded on the session by a prior successful entry. With no
recorded profile there is nothing to replay and the supervisor does nothing: it never invents
credentials or a login path it hasn't been handed. Reconnect is **bounded** — a fixed number of
attempts with a backoff between them; exhausting them stops the burst (a later poll tick naturally
retries once the socket is still down), it does not spin forever.

The goal is an **invisible resume**: where the reconnect + replay succeeds, the driving surface sees
the session return to its command screen without having to detect the drop or re-issue anything. But
invisibility is a best-effort convenience, never a licence to fake success — see the reconnect ×
control contract below.

# Login-Replay & Resume Verification

Reconnect re-opens the socket; **login-replay** drives the freshly-reconnected session back to the
command screen. It replays the *same* classification-driven login automaton that
[the Login Automaton](/architecture/login-automaton.md) uses for a first entry — the reactive,
order-independent expect/respond engine — targeting the `main_command` classification. Replay uses
the **saved credential for the existing character**, sent exactly as the automaton sends it: through
the redacted send path, `secret=True`, so it routes to `log_redacted()`. The password never touches
the supervisor's return values, exceptions, or any log line — the secrets-never-touch-logs invariant
is preserved verbatim through recovery. A returning login never regenerates or guesses a password: a
missing or stale saved credential is a hard, loud failure, not something to brute-force.

**Resume verification is the boundary between "recovered" and "returned to control."** The replay
does not report success on merely reconnecting, or on sending its last keystroke — it succeeds only
when the automaton positively reaches `main_command`. If the automaton cannot make progress to that
target — a repeated unrecognized screen, an exhausted step budget, a bad saved credential — it
raises rather than declaring victory on an unverified screen. The resumed screen must be *verified as
known* before control is handed back; anything short of that is an escalation event, not a resume.

# Conservative Idle-Keepalive

The keepalive prevents the drop the reconnect logic would otherwise have to repair. When the session
has been idle — no bytes in either direction — past a bounded threshold set comfortably under the
server's first inactivity warning, the supervisor sends a single harmless blank keystroke to reset
the server's inactivity clock. The observed live warning ladder is roughly "sixty seconds → thirty
seconds → ten seconds → terminated," and the threshold sits well under the first rung. [Verification
status: the specific threshold and warning ladder are drawn from live session logs against one TWGS
server; treat the exact seconds as observed-not-guaranteed across server configs.]

The keepalive is governed by one hard **safety invariant**: it fires **only** on the single safest
screen — the main command prompt — and is **OFF on every other screen.** It never nudges a screen
where a stray blank Enter could accept an unintended default or commit an action:

- **Never** on a password/credential prompt — a blank Enter would desync a pending credential
  exchange.
- **Never** on a purchase, trade, or port screen — "How many holds… [50]?" treats a blank Enter as
  *buy 50*. A keepalive that commits money is not a keepalive.
- **Never** on a confirm/yes-no or combat screen — a blank Enter could confirm a destructive action
  or a fight.

This is the same doctrine that governs the whole client: an unrecognized-or-unsafe screen is never
nudged, defaulted, or guessed. The keepalive classifies the current screen and stays its hand unless
that classification is unambiguously `main_command`. Because the keepalive *does* emit a live
keystroke, it is an **App-class send** in the actor model — the App (via its supervisor) is the
sender, `{app, human}` are the only live senders, and the keepalive nudge is attributed to the App,
never to any AI (the AI never emits a live keystroke — see
[Control & Escalation](/architecture/control-and-escalation.md)).

# The Reconnect × Control Contract

Resilience serves the control model; it does not get to bypass it. The contract has one governing
rule: **a post-resume unknown screen escalates to the Human — it is never an autonomous recovery
guess.**

- **Verified resume → return to whoever was driving.** If login-replay verifies the session back at
  `main_command`, control returns to the pre-drop driver (App autopilot or Human) and the resume can
  be as invisible as the reconnect allowed.
- **Unverified / unknown resume → STOP and hand the keyboard to the Human.** If reconnect exhausts
  its attempts, or login-replay cannot reach a known command screen, or the session comes back on a
  screen the automaton doesn't recognize, the supervisor must **not** improvise a recovery — no blind
  keystroke, no default, no "try something." This is exactly the escalate-on-unknown mechanic that
  governs the App autopilot, applied at the connection layer: the App stops, the reason is surfaced,
  and the Human — the sovereign pilot and escalation target — takes the keyboard. Recovery of an
  unknown post-drop state is a human decision, never an autonomous one.

This closes the loop with [Control & Escalation](/architecture/control-and-escalation.md): the App
drives only screens it can positively recognize, and the connection layer is held to the same bar. A
drop is a connection event the supervisor may transparently repair; an *unrecognized* post-drop
screen is a control event the supervisor must escalate.

# Schema

| Facet | Trigger | Bounded by | Action | Safety rule |
|---|---|---|---|---|
| Drop detection | Poll tick sees connection flag false | Poll interval | Enter reconnect flow | Only if a prior successful login was recorded |
| Reconnect | Socket dropped + recorded profile | Max attempts + backoff | Re-open the one connection (no 2nd daemon) | Never invents credentials or a login path |
| Login-replay | Reconnect succeeded | Automaton step budget | Replay same automaton to `main_command` with saved credential | Password via redacted `secret=True` send; returning login never guesses/retries a stale password |
| Resume verification | Replay finished | — | Confirm classification == `main_command` before returning control | Unverified/unknown → escalate, never declare success |
| Idle-keepalive | Idle past threshold (< first inactivity warning) | Threshold + single blank keystroke | Send one blank Enter | **ONLY** on `main_command`; OFF on password/trade/confirm/combat/unknown |
| Reconnect × control | Post-resume screen unknown or recovery exhausted | — | STOP + hand keyboard to Human | Never an autonomous recovery guess |

# Examples

An invisible resume across a server kick:

```
1. App is autopiloting a trade loop. The server kicks the socket during a lull.
2. Next poll tick: the supervisor sees the connection flag is false and a login
   profile was recorded. It reconnects the one session (no second daemon) and
   replays the login automaton with the SAVED credential (secret send, redacted log).
3. The automaton reaches main_command. Resume is verified. Control returns to the App,
   which resumes autopiloting from the command screen — the driving surface never had
   to notice the drop.
```

A keepalive that correctly declines to fire:

```
1. The session has been idle, sitting on a port trade screen ("How many holds [50]?").
2. Idle time crosses the keepalive threshold.
3. The supervisor classifies the current screen: port_trade, not main_command.
4. It sends NOTHING. A blank Enter here would buy 50 holds. The keepalive stays OFF
   on every screen but the single safest one, so the session is allowed to risk the
   idle-timeout drop rather than commit an unintended purchase — and the reconnect
   path (above) is what covers the drop if it comes.
```

An unrecoverable resume that escalates instead of guessing:

```
1. The socket drops. The supervisor reconnects but the saved password is stale;
   login-replay cannot reach main_command and raises rather than declaring success.
2. Reconnect attempts are exhausted. The supervisor does NOT improvise — no blind
   keystroke, no default.
3. STOP: the App halts and hands the keyboard to the Human with a clear reason.
   The Human — sovereign pilot and escalation target — takes over and recovers the
   session (re-entering the password, or fixing the profile) by hand.
```

# Code Divergence

The current `tw2002_aiclient/session/guardian.py` implements the reconnect + login-replay + keepalive
facets as this canon prescribes for the mechanical parts — drop-detection via the connection flag,
bounded-attempt reconnect gated on a recorded `auto_login_profile`, login-replay via `run_login(...,
target="main_command")` with the saved credential through the redacted secret path, and a keepalive
that fires **only** when the current screen classifies as `main_command`. Those match the reborn
target. (Archive port-source: `twclient/guardian.py`.)

**Reconnect × control (shipped WO-FIX-SESSIONGUARDIAN-EXHAUSTED-RECONNECT-SILENT).** When
reconnect + replay exhausts all attempts, the guardian sets a sticky `reconnect_exhausted` flag that
suppresses further auto-retry (no silent forever-poll), records `last_reconnect_error`, and the
`status` verb surfaces typed reason `reconnect_exhausted` on `status["intervention"]` for the STOP
banner. There is **no** auto-`MODE_HUMAN` — keyboard escalate stays operator-driven (attach / teach
moves). The sticky clears on a successful D9 reconnect, on `clear_reconnect_exhausted()`, or when a
later tick observes the socket already connected again (manual ensure).

(Minor, sub-divergence: the keepalive's blank Enter is a live App-class keystroke but is not yet
explicitly actor-tagged `app` at the send site — the send-time actor tag is owned by
[the Session Engine](/architecture/session-engine.md); this concept only notes that the keepalive is,
canonically, an App-class send.)

# Citations

[1] `tw2002_aiclient/session/guardian.py` (SessionGuardian — reconnect, login-replay, idle-keepalive; ported from archive `twclient/guardian.py`)
[2] `tw2002_aiclient/session/login.py` (run_login automaton replayed on resume; saved-credential / secret-send discipline)
[3] `tw2002_aiclient/session/connection.py` (TelnetConnection reader thread, connection flag, redacted send path)
[4] canon/architecture/control-and-escalation.md (escalate-on-unknown, the App/Human dual)
[5] DESIGN-v2.md §3 v2.1 item 4 (D9 reconnect + login-replay; D10 conservative idle-keepalive)
