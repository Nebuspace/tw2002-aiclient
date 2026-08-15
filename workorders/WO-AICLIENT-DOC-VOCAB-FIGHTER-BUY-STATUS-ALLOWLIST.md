# WO-AICLIENT-DOC-VOCAB-FIGHTER-BUY-STATUS-ALLOWLIST

**Goal:** Tip-honest `STARVED_ALLOWLIST` reason for `fighter_buy_status`.

**Tip note:** The key remains intentionally unwritten (optional override).
GOALS already derives the Fighters detail via `afford_fighters` when the
key is absent — the old reason ("needs shipyard-screen parsing") was
tip-false for the display path.

**Scope:**
- `tests/test_status_vocabulary_guard.py` — allowlist reason + pin
- `tw2002_aiclient/cockpit/goals.py` — docstring on
  `_fighter_buy_status_from_status`

**Accept:**
- Allowlist reason cites derived-via-`afford_fighters` / optional override
- Does not claim shipyard parsing blocks display
- Guard suite green

**Proof:**
- `.venv/bin/python -m pytest tests/test_status_vocabulary_guard.py -q`
- `live-prove: n/a` — docs/test-only tip honesty
