# WO-P2-023 — Login NEW vs RETURNING

> Status: PLANNED (greenfield · HOLD-GATES-PENDING blocks execution until a lifting HANDOFF)
**Phase:** 2 · **Type:** harden · **Depends:** WO-P2-020
**Canon:** `canon/architecture/login-automaton.md` (NEW vs RETURNING)

**Goal:** Implement the classification-driven login automaton's structural branch — a password gate
reached without a "start a new character?" screen means RETURNING (send saved password once); a
"start a new character?" screen means NEW (gated behind explicit per-profile `allow_register`
opt-in, refused before the first registration keystroke otherwise).

**Scope:** `tw2002_aiclient/session/login.py` (new — `run_login()`, `_decide()`), `tw2002_aiclient/session/classify.py` (gate
anchors for handle prompt / password gate / "start a new character?").

**Accept:**
- A RETURNING profile (handle already registered on the target server) reaches `Command [TL=…]`
  using the saved password sent exactly once, resolved via `get_password()` (WO-P0-005's env-first
  precedence).
- A profile with `allow_register = false` that hits a "start a new character?" screen is refused
  **before** the `Y` keystroke is sent — a typed `registration_not_permitted` error is raised, no
  character is created.
- A profile with `allow_register = true` completes registration: password generated and **saved
  before the first send**, cosmetic sub-steps answered from profile-supplied pools, target reached.
- A wrong/stale saved password on the RETURNING path is a hard, fail-loud failure — never retried
  past a small fixed ceiling, never guessed.

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/pytest tests/test_login.py -k "returning or new_registration or refused" -q
# live fixture (staging server) for at least one RETURNING full-arc run:
.venv/bin/python -m tw2002_aiclient.session.cli ensure --profile <returning-profile>
```
