# WO-DEAD-TERMINAL-SPIN-INTERMITTENT

**Goal:** Get a structural account of (or honest KEEP-with-evidence for) intermittent failures in `tests/test_dead_terminal_spin.py` promptness/rusage assertions.

**Context (from #181 STATUS):** Failed once in four full-suite runs under unquantified load; pass in isolation and in three subsequent full runs. First attribution (two concurrent pytest masters) was a measurement error (`grep -c` counts wrapper+process). Open observation — not claimed flaky without structure.

**Scope:** `tests/test_dead_terminal_spin.py` (+ helpers it depends on). Diagnose-first; fix only with a falsifiable root cause. Do not weaken Accept criteria without hub ACK.

**Constraints:** Refuse missing/unrecognised instrument readings as favourable. Certify via `--junitxml` / explicit counts. live-prove `n/a` unless a live PTY path is implicated with evidence.

**Accept:**
1. Reproduce under controlled conditions **or** document why unreproducible with the exact probes used.
2. Structural root cause **or** banked KEEP-observation with what would falsify "load flake."
3. If fix: injection RED / fixed GREEN + suite green.

**Proof:** STATUS with reproduction protocol + evidence; suite CI if code changes.

**Refs:** #181 process item 2 · `test_dead_terminal_spin.py`.
