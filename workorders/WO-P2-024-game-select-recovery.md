# WO-P2-024 — Game-select recovery

> Status: DONE (shipped `4b41908` 2026-07-24 — login.py unchanged: reactive design already resumes; proven by tests/test_login_resume.py 4 tests + fake_twgs resume API)
**Phase:** 2 · **Type:** harden · **Depends:** WO-P2-020
**Canon:** `canon/architecture/login-automaton.md` (The Automaton Is Reactive, Not a Script —
idempotent resume)

**Goal:** Prove a session stuck mid-flow on the server door-select ("Select a game :") screen can be
recovered by a fresh `ensure` call without desyncing — the reactive, screen-keyed dispatch resumes
the unmet suffix rather than requiring a cold restart.

**Scope:** `tw2002_aiclient/session/login.py` (no new code beyond WO-P2-023 if the reactive design already holds;
this WO is primarily a verify/harden pass proving the resume path).

**Accept:**
- Manually landing a session on the game-select screen (e.g. via `tw do` sending a partial login
  sequence and stopping) and then calling `ensure` again reaches `main_command` without the
  automaton re-sending steps already completed or double-answering the door-select prompt.
- The recovery works identically whether the stuck screen is the door-select menu or a later
  interstitial (e.g. "Show today's log?") — the automaton's screen-keyed dispatch, not a step
  counter, drives resume in both cases.

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/python -m tw2002_aiclient.session.cli start --host <h> --port <p>
.venv/bin/python -m tw2002_aiclient.session.cli do "<enter>"   # stop partway, e.g. right at door-select
.venv/bin/python -m tw2002_aiclient.session.cli ensure --profile <profile>   # resumes and reaches main_command
.venv/bin/python -m tw2002_aiclient.session.cli status --json | python3 -m json.tool
```
