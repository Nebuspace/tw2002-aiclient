# WO-P2-027 — Reconnect + login replay

> Status: PLANNED (greenfield · HOLD-GATES-PENDING blocks execution until a lifting HANDOFF)
**Phase:** 2 · **Type:** build · **Depends:** WO-P2-020, WO-P2-023
**Canon:** `canon/architecture/resilience-and-reconnect.md` (Drop Detection & Reconnect,
Login-Replay & Resume Verification)

**Goal:** Build the `SessionGuardian` background poller that detects a dropped socket and recovers
by reconnecting the same daemon (never a second connection) and replaying the login automaton to a
**verified** `main_command`, so a spectate or play session survives a socket recycle.

**Scope:** `tw2002_aiclient/session/guardian.py` (new — poll loop, drop detection via the connection flag, bounded
reconnect attempts, login-replay call into `tw2002_aiclient/session/login.py`).

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
