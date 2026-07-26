# WO-P2-027 — Reconnect + login replay

> Status: **DONE** · origin `e1f189c` (hub Accept stamp 2026-07-26 · was EXECUTE DONE awaiting Accept)
**Phase:** 2 · **Type:** build · **Depends:** WO-P2-020, WO-P2-023
**Canon:** `canon/architecture/resilience-and-reconnect.md` (Drop Detection & Reconnect,
Login-Replay & Resume Verification)

**Goal:** Build the `SessionGuardian` background poller that detects a dropped socket and recovers
by reconnecting the same daemon (never a second connection) and replaying the login automaton to a
**verified** `main_command`, so a spectate or play session survives a socket recycle.

**Scope:** `tw2002_aiclient/session/guardian.py` (new — poll loop, drop detection via the connection flag, bounded
reconnect attempts, login-replay call into `tw2002_aiclient/session/login.py`).

**Out of bounds (prep + until execute HANDOFF):** `credentials.py` · resolver · `env.py`/`cli.py`/`protocol.py`
edits while OPEN-003-A in flight · product keepalive (WO-P2-028) · full escalate-to-Human control-layer
wiring (fail-loud + no false success is in-scope; STOP+keyboard handoff may follow).

---

## PREP inventory (2026-07-24 — WO-P2-027-PREP · parallel fan-out)

### Verify-first verdict

**Supervisor missing; plumbing mostly live.** No live `guardian.py` (daemon notes unported at
`daemon.py:12–14`; archive twin only). Drop flag, same-daemon `Session.reconnect()`,
`auto_login_profile` / `mark_profile`, and `run_login(..., target="main_command")` with
`secret=True` already match canon. Execute = **port SessionGuardian** (poll + bounded reconnect +
login-replay), not rebuild login/reconnect primitives.

### Live surface (file:line)

| Canon / Accept behavior | Where | vs canon |
|-------------------------|-------|----------|
| `SessionGuardian` poll loop (~few s) | — | **GAP** (archive `twclient/guardian.py`) |
| Drop = `conn.connected is False` | `connection.py:40–59` | **match** |
| Reconnect same daemon / single pidfile | `session.py:142–163` + `daemon.py:113–188` | **match** plumbing |
| Only if prior successful login recorded | `session.py:107–110`, `mark_profile` `137–140` | **match** hook (unused w/o guardian) |
| Bounded attempts + backoff | — | **GAP** (archive defaults poll 2s / backoff 3s / max 5) |
| Login-replay via `run_login` → `main_command` | `login.py:167–205` | **match** API; no live guardian caller |
| Resume success iff verified `main_command` | `login.py:204–205` (else raise) | **match** |
| Password via `secret=True` / redaction | `login.py:238–244`; `connection.py:71–77`; `session.py:235–254` | **match** |
| Exhausted / unverified → STOP+Human | — | **GAP** (fail-loud first; escalate wiring follow-up) |
| Idle keepalive on `main_command` only | — | **out of scope** → WO-P2-028 |

### Accept (tightened draft for execute)

- Drop on poll when `conn.connected is False`; reconnect **only** if `auto_login_profile` is set (no profile → zero reconnects, no invented credentials).
- Reconnect uses `session.reconnect()` under the **same** daemon; pidfile/`run/twd.pid` count stays **1** for the recovery window.
- First attempt within one `poll_interval_s` of the drop (default **2.0s**; injectable).
- Burst bounded: ≤ `max_reconnect_attempts` (default **5**) with `reconnect_backoff_s` (default **3.0s**); exhaustion does not spin forever and does **not** report resume success.
- Login-replay = saved credential through `send(..., secret=True)` → `log_redacted`; password never in guardian returns, exceptions, or logs; missing/stale credential → loud fail.
- Resume success **iff** classification is verified `main_command`. Unrecognized / stuck / step-budget exhaust → no success, no blind keystrokes.
- After verified resume, `status`/`spectate` observers see `connected: true` with no surface-side re-issue.
- Keepalive / D10 and full escalate-keyboard handoff: **not** this WO’s green bar (028 / follow-up).

### Proof (tightened draft)

```bash
cd "$(git rev-parse --show-toplevel)"
# un-ignore / rewrite reconnect slice of tests/test_guardian.py under execute
.venv/bin/pytest tests/test_guardian.py -k 'reconnect' -q
# unit must cover: no-profile skip · secret=True · verified main_command ·
# failed-then-succeed · max-attempts give-up · no-saved-password · unverified ≠ success
.venv/bin/python -m tw2002_aiclient.session.cli ensure --profile <profile>
# force socket drop (fault hook / kill FD — not pidfile); wait ≤ poll_interval
.venv/bin/python -m tw2002_aiclient.session.cli status --json | python3 -m json.tool  # connected: true
# assert single daemon/pidfile owner through recovery
grep -iF "<password>" logs/session-*.log; test $? -eq 1
```

### Tests touch list

| File / slice | Role under 027 |
|--------------|----------------|
| `tests/test_guardian.py` `-k reconnect` (~5) | **Primary** — ignored DEFER today; rewrite/un-ignore on execute |
| `tests/test_guardian.py` `-k keepalive` | **WO-P2-028** — leave ignored |
| `tests/test_login_resume.py` / `fake_twgs` resume | **WO-P2-024** DONE — do not retouch |
| `tests/test_session.py` reconnect game-select | session greenfield — not guardian |
| spectate / protocol / attach “reconnect\|resume” hits | **other owners** — out of 027 |

### Edge cases (pin in tests)

| Edge | Expected |
|------|----------|
| No `auto_login_profile` | 0 `reconnect()` calls |
| Second daemon / new pidfile | Forbidden — same session / single pid |
| Password send | Exactly one secret send of saved pw; no `save_password` on returning path |
| Unverified screen after socket up | No success; error recorded; no blind keystroke |
| Poll interval | Drop → first attempt ≤ `poll_interval_s` |
| Exhausted attempts | Stops at max; not reported as resumed |
| Keepalive | Not this WO |

---

## Original Accept / Proof (pre-prep)

**Accept:**
- Killing the underlying socket (or the daemon's connection) while a profile has a prior successful
  login recorded results in an automatic reconnect within the poll interval, using the same daemon
  (no second `run/twd.pid`).
- Login-replay uses the saved credential through the redacted `secret=True` send path — the password
  never appears in any log line produced during recovery.
- Resume is reported successful only once the automaton **positively verifies** `main_command` — a
  reconnect that lands on an unrecognized screen is not reported as a successful resume.
- `tw spectate` or `tw status` polling through the recovery window shows the session return to
  `connected: true` without the calling surface having to detect or re-issue anything.

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/python -m tw2002_aiclient.session.cli ensure --profile <profile>
# in another terminal, force-kill the daemon's socket (not the pidfile) or use a fault-injection test hook
.venv/bin/pytest tests/test_guardian.py -k reconnect -q
.venv/bin/python -m tw2002_aiclient.session.cli status --json | python3 -m json.tool   # connected: true after recovery
grep -i "<password>" logs/session-*.log   # expect no match — nothing leaked during replay
```
