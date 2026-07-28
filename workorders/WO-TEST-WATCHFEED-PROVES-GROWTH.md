# WO-TEST-WATCHFEED-PROVES-GROWTH

**Goal:** Make the assert prove what its comment claims (growth, not a single event).

**Scope:** `tests/test_watchfeed.py`

**Accept:** A feed delivering exactly one event then stalling **fails**; the real feed still passes.

**Proof:** injected single-event feed reddens; suite. live-prove `n/a`.

**Refs:** #188 F2.
