# WO-TEST-RACE-PIN-COST

**Goal:** Cut wall-clock of `test_a_send_racing_a_read_never_yields_a_stale_positive` without weakening the concurrency invariant it pins.

**Context:** The test issues **300** sends; `Session.send` sleeps up to `MIN_SEND_GAP_S` (0.15s) before each write → ~45s alone. Dominates falsification harnesses that exclude it via `-k "not racing"` and still burns full-suite CI. Banked from #177 STATUS (CC): real pin, not proposed to delete — ask whether a **smaller count** and/or a **shrunken gap under test** proves the same thing.

**Scope (owned paths):**
- `tests/test_last_known_sector.py` (`test_a_send_racing_a_read_never_yields_a_stale_positive`)
- Optionally a test-only monkeypatch of `MIN_SEND_GAP_S` / send-gap in that test module only — **not** production defaults

**Constraints:**
- Do **not** weaken the race assertion (stale-positive must still be impossible under concurrent read).
- Do **not** change production `MIN_SEND_GAP_S` for live/TWGS anti-hammer.
- Prefer evidence: show N≪300 (or gap≪0.15 under test) still fails a deliberate broken injection, then green on the fixed tree.
- live-prove `n/a` (offline test cost only).

**Accept:**
1. Race pin still fails an intentional injection that would yield a stale positive.
2. Wall-clock of the single test drops materially (target: order-of-magnitude or at least ≤~5s on a quiet box — report before/after).
3. Full suite green; STATUS cites junit or terminal summary with counts (refuse empty/unrecognised as favourable).

**Proof:** before/after timing of the one test + injection RED / fixed GREEN; suite CI.

**Refs:** `tests/test_last_known_sector.py` · `MIN_SEND_GAP_S` in `session/session.py` · #177 falsification disclosure.
