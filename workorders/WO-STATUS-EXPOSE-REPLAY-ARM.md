# WO-STATUS-EXPOSE-REPLAY-ARM — the field that arms a credential replay is invisible to the operator

**ID:** WO-STATUS-EXPOSE-REPLAY-ARM
**Branch:** `wo/STATUS-EXPOSE-REPLAY-ARM`
**Seat:** unassigned (hub to route)
**Priority:** HIGH (honesty on a credential surface) — but **GATED**
**Size:** S (one response field + tests)
**Banked by:** `impl-claudecode-aiclient`, 2026-07-28, per hub ruling @ 07:18:00Z
**Status:** OPEN · EXECUTE · HIGH · Max GO 2026-07-28 (honesty / shop-stop) · Cursor preferred

---

## Goal

`tw status` should report the **replay arm**: which profile a reconnect would replay, and the
`(host, port)` it would replay against — so the armed state is inspectable by the person
responsible for it.

## Background — measured on tip

`session.auto_login_profile` governs unattended credential replay. Its complete reader set is
**two lines**:

- `guardian.py:134` — `if not session.auto_login_profile: return`
- `guardian.py:145` — `profile = load_profile(session.auto_login_profile)`, immediately
  followed by `session.reconnect()` and `run_login(..., get_password=...)`

**The single consumer of this field is the thing that sends a password.**

Writers: `protocol.py:1235`, `:1263` (both now behind the WO-ENSURE-PROFILE-IDENTITY-VERIFY
gate), plus `session.py:159` init.

**Response payloads exposing it: zero.** `protocol.py:1174` reads an *argument*, not emits one.
`tw status --json` returns `host`, `port`, `classification`, `mode`, `autopilot`,
`subscribers`, `log_tail`… and no profile field at all.

`guardian.start()` is **unconditional** in `daemon.main()` (`daemon.py:632-635`). It is inert
only while `auto_login_profile` is `None`; **one successful `ensure` arms it for the daemon's
lifetime.**

So an operator cannot answer: *"if this link drops right now, whose credential does my daemon
send, and where?"* The product knows. It never says.

### How this was found

The WO-ENSURE-PROFILE-IDENTITY-VERIFY live-prove tried to assert that a refused `ensure` had
not relabelled the session, by reading `status`. It returned `profile=None` — **not because
the relabel was suppressed, but because the field is not exposed at all.** The assertion was
structurally incapable of failing and was retracted. The gap in the product is what made a
safety assertion vacuous; that is the strongest possible argument that it matters.

## Scope

| Action | Path |
|---|---|
| Add replay-arm reporting to the status response | `tw2002_aiclient/session/protocol.py` |
| Tests | `tests/` |

**Out of bounds — hard:** credential handling, the login automaton, `guardian.py` logic, and
anything that changes **how, whether, or where** a credential is sent. This WO is
**read-only reporting**. If an implementation finds itself editing a send path, it has left
scope.

## Secrets doctrine

Profile **name** only. Never the password, never a secret-store path, never a key.
`host`/`port` here are the operator's own config and are already returned by `status` today —
this adds no new class of disclosure. See `canon/doctrine/secrets-and-credentials.md`.

## Accept

- After `ensure --profile X`, `status --json` reports the arm: profile name + the
  `(host, port)` a reconnect would target.
- Before any successful `ensure`, it reports **disarmed** — and disarmed is distinguishable
  from "field missing" (an absent key must not read as safe).
- The reported value tracks `mark_profile` exactly — it is the same field, not a
  re-derivation that could drift from it.
- No password, secret path, or credential material appears in any response.

## Proof

Extend the WO-ENSURE-PROFILE-IDENTITY-VERIFY fake-TWGS harness: it already stands a real
daemon over the real unix socket against a local `FakeTWGS`, so the arm becomes
**live-observable** and the retracted assertion becomes a real one — assert the key is
**present**, then assert its value, in both the armed and disarmed states.

## Why this is gated

`ensure` is the login money-path and this field arms a credential send. Per the hard rule,
auth/credential surfaces are diagnosed freely and **fixed only with Max's OK**. Two questions
for the ruling:

1. Bank + build, or leave the arm unreported?
2. Is read-only *exposure of a profile name* inside the hub's ungated envelope, or does it
   want Max specifically?

## Refs

- `canon/doctrine/secrets-and-credentials.md`
- `canon/architecture/resilience-and-reconnect.md`
- `workorders/WO-P2-027-reconnect-login-replay.md` (DONE — built the guardian; did not expose its arm)
- Coord: `impl-claudecode-aiclient` @ 2026-07-28T07:17Z · hub ACK @ 07:18:00Z
