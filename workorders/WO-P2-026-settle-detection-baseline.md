# WO-P2-026 — Settle detection baseline

> Status: PLANNED (greenfield · HOLD-GATES-PENDING blocks execution until a lifting HANDOFF)
**Phase:** 2 · **Type:** verify/harden · **Depends:** WO-P2-020
**Canon:** `canon/architecture/settle-detection.md`

**Goal:** Implement the three settle conditions (`prompt`/`idle`/`timeout`) with the case-sensitive
`wait_prompt` invariant intact, so no downstream consumer ever acts on a mid-transition frame.

**Scope:** `tw2002_aiclient/session/settle.py` (new — `wait_for_settle`, `wait_until_settled`, `send_and_confirm`),
`tw2002_aiclient/session/session.py` (settle-detection bookkeeping fields: `rx_count`, `last_rx`, `clock`).

**Accept:**
- A `do` call with a matching `--wait-prompt` regex returns `settled_reason: prompt`.
- A `do` call with no `wait_prompt` and a quiet screen returns `settled_reason: idle` only after
  ≥1 byte has arrived since the send (never on an instantaneous zero-byte quiet).
- A `wait_prompt` that mismatches only on letter case does **not** raise — it silently falls through
  to `timeout` (proves the case-sensitivity invariant is intact, not "helpfully" case-folded).
- A bounded wait budget elapsing with no positive settle returns `settled_reason: timeout`, never a
  pretend-settled frame.

**Proof:**
```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/pytest tests/test_settle.py -q
.venv/bin/python -m tw2002_aiclient.session.cli do "1" --wait-prompt "Command \[TL="       # settled: prompt
.venv/bin/python -m tw2002_aiclient.session.cli do "1" --wait-prompt "command \[tl="       # case mismatch -> settled: timeout
```
