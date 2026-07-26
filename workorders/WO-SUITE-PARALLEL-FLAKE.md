# WO-SUITE-PARALLEL-FLAKE

**Status:** OPEN · tests · Claude Code lane · self-banked 2026-07-26
**Posted:** 2026-07-26 · after `61bdea2`

## Goal

The suite fails intermittently under its own default `-n auto`. Two different tests failed on two
consecutive full runs; a serial run was clean. Make the suite's default invocation trustworthy, or
make the untrustworthy cells honestly serial — but stop shipping a suite whose green depends on how
busy the machine was.

## Why this matters more than it looks

Every certification in this project is *"suite green, therefore no regression."* **A suite that fails
a different test each run silently converts that into "suite green, therefore probably no
regression, unless it was luck."** Worse, it trains the reflex this project explicitly refuses
elsewhere: *"just run it again."* I have rejected three-greens-on-a-flake reasoning in other people's
work this session; the suite should not require it of me.

It also costs real evidence: a genuine regression arriving now would be indistinguishable from the
ambient noise, and would very likely be dismissed as "the usual flake."

## Observed (tip `61bdea2`)

```
run 1  -n auto : FAIL tests/test_do_settle_rx_guard.py::test_do_returns_on_real_wall_clock_time_when_the_game_says_nothing
run 2  -n auto : FAIL tests/test_login.py::test_registration_refused_raises_before_any_char_create_send
run 3  -n0     : 3376 passed, 0 failed
```

Different test each run ⇒ not a regression; a regression fails the same test every time.

## Diagnosis — one characterized, one NOT

**A. `test_do_settle_rx_guard.py` — characterized.** It asserts **UPPER bounds on real wall-clock
elapsed time**:

```
assert resp["elapsed"] >= 0.8
assert resp["elapsed"] <  1.0        # 200ms window
assert 0.5 <= resp["elapsed"] < 0.6  # 100ms window
```

The file's own docstring says it uses real `time.monotonic()` and real `time.sleep()` deliberately.
**The LOWER bounds are the property under test** — they prove the code actually waited. **The UPPER
bounds assert something else entirely: that the machine was not busy.** Under `-n auto` (one worker
per core, all saturated) a 100 ms ceiling on wall-clock is violated by scheduling, not by the code.

**B. `test_login.py::test_registration_refused_raises_before_any_char_create_send` — NOT diagnosed.**
It takes only `tmp_path` and drives a fake session; no shared-state cause is visible from a read.
**Do not invent one.** Diagnose it or report honestly that it is undiagnosed — an unexplained flake
left unexplained is a better outcome than a plausible story that closes the ticket.

## Scope

- `tests/` only. **No product code.** If a test flake turns out to be a genuine product race, STOP
  and report — that is a different WO and a much more serious one.

## Constraints

- **Do not weaken a real assertion to buy a green.** The lower bounds prove the wait happened and
  must survive. Deleting an upper bound is acceptable only where it asserts machine idleness rather
  than program behavior — say which, per assertion.
- **Do not blanket-mark tests `flaky`/`rerun`.** A retry decorator is the "run it again" reflex
  encoded in the suite, and it would hide the next real race permanently.
- Marking genuinely timing-dependent cells as serial-only (or giving them generous ceilings that
  still fail on a real hang) is acceptable **if argued per cell**.
- Do not change the default `-n auto`; a suite that must run serially to pass is a finding, not a fix.

## Accept

Ten consecutive `-n auto` full runs, zero failures. Every changed assertion justified individually as
either (a) machine-idleness, not behavior, or (b) genuinely serial. Test B either diagnosed or
explicitly reported as undiagnosed with what was ruled out.

## Proof

STATUS + SHA · the 10-run log with counts · per-assertion justification · full-suite count from
junitxml after process exit (baseline **3376**) · tree md5 fingerprint bracketing.

**Note on the bracket:** another seat may be editing this shared tree concurrently. If the
fingerprint moves mid-run, do not re-run blindly — establish whether the end-state tree equals what
you are certifying, and say so.

## Refs

CC STATUS 2026-07-26T10:27:27Z (suite-health finding) · `61bdea2`
