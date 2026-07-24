# WO-P2-026 — Settle detection baseline

> Status: PLANNED (greenfield · **PREP DONE** 2026-07-24 · product execute blocked until lifting HANDOFF)
**Phase:** 2 · **Type:** verify/harden · **Depends:** WO-P2-020
**Canon:** `canon/architecture/settle-detection.md`

**Goal:** Implement the three settle conditions (`prompt`/`idle`/`timeout`) with the case-sensitive
`wait_prompt` invariant intact, so no downstream consumer ever acts on a mid-transition frame.

**Scope:** `tw2002_aiclient/session/settle.py` (`wait_for_settle`, `wait_until_settled`, `send_and_confirm`),
`tw2002_aiclient/session/session.py` (settle bookkeeping: `rx_count`, `last_rx`, `clock` / `wait_settle`).

**Out of bounds (prep + until execute HANDOFF):** `credentials.py` · resolver · `env.py`/`cli.py`/`protocol.py`
edits while OPEN-003-A in flight · per-screen profile **registry** / interjection absorb (canon later
slices — not the baseline kernel).

---

## PREP inventory (2026-07-24 — WO-P2-026-PREP · parallel fan-out)

### Verify-first verdict

**Kernel already live.** `settle.py` (~304 lines) + greenfield `tests/test_settle.py` (**24 passed**
this prep) already implement prompt / idle / timeout, ≥1-byte idle guard, case-sensitive
`wait_prompt` (`re.compile` **without** `IGNORECASE` at `settle.py:71–75`), stale pre-send match
guard, and `send_and_confirm` stability recheck (+ `retry_unstable_idle`).

Execute HANDOFF should be **verify + thin gaps**, not from-scratch port.

### Live surface (file:line)

| Behavior | Where | vs canon |
|----------|-------|----------|
| Three reasons `prompt`/`idle`/`timeout` | `settle.py:67+` `wait_for_settle` | **match** |
| Case-sensitive `wait_prompt` | `settle.py:71–75` | **match** (hard rule comment) |
| Idle requires ≥1 byte since wait start | idle path in `wait_for_settle` / tests | **match** |
| `wait_until_settled` (pre-send quiet OK) | `settle.py` + tests | **match** (extra vs bare Accept) |
| `send_and_confirm` + stability pause | `settle.py` ~send_and_confirm; tests | **match** warp-aware *mechanism* |
| Session wrapper | `session.py:214–231` `wait_settle` → settle | **match** |
| Login uses `send_and_confirm` | `login.py` (read-only cite) | **match** call site |
| Declarative per-screen settle **profile registry** | — | **gap** (canon later; out of baseline) |
| Interjection absorb registry | — | **gap** / other concept |
| CLI `do` + `--wait-prompt` Proof lines | `cli.py` only `status`/`ensure` today | **gap** for WO Proof as written |

### Accept (tightened draft for execute)

- Unit: matching `wait_prompt` → `settled_reason == "prompt"` (already covered).
- Unit: no prompt + quiet after ≥1 byte → `"idle"`; zero bytes ever → `"timeout"` not idle (covered).
- Unit: **explicit case-mismatch** `wait_prompt` (e.g. `command \[tl=` vs `Command [TL=`) → `"timeout"`, never raise, never match — **add if missing** (no dedicated test name today).
- Unit: budget elapse → `"timeout"`, never pretend-settled / `confirmed=True` without match (covered via `send_and_confirm`).
- Optional: wire `cli do` only if a Phase-2 verb WO lands; else Proof stays pytest-only (docs-win: update Proof block).

### Proof (tightened draft)

```bash
cd "$(git rev-parse --show-toplevel)"
.venv/bin/pytest tests/test_settle.py -q
# add when execute: case-mismatch unit in test_settle.py
rg -n "IGNORECASE" tw2002_aiclient/session/settle.py   # expect no match on wait_prompt compile
```

### Tests touch list

| File | Role under 026 |
|------|----------------|
| `tests/test_settle.py` | **Already greenfield / primary** — extend with case-mismatch + any Accept gaps |
| Rehab ignored settle-adjacent | **None dedicated** in §REWRITE — guardian/skills that call settle stay DEFER until those modules port |
| `tests/test_login.py` | Uses settle indirectly — **CC exclusive**; do not touch in 026 execute |

---

## Original Accept / Proof (pre-prep)

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
