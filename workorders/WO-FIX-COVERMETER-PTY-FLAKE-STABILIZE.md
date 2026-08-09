# WO-FIX-COVERMETER-PTY-FLAKE-STABILIZE

**Status:** DONE
**Seat:** `impl-aiclient-cursor`
**Branch:** `wo/FIX-COVERMETER-PTY-FLAKE-STABILIZE`
**Depends:** `main` @ `e554971`

## Why

`tests/test_cockpit_covermeter_pty.py::test_coverage_meter_is_visible_on_a_real_terminal`
and `::test_meter_reads_honest_unknown_not_a_fabricated_share` were cited as
permanent PTY-sandbox noise across several unrelated WOs (e.g.
`WO-BUILD-MACRO-CAPTURE-PARAM-GENERALIZATION-2`'s Proof section: "the two
covermeter PTY tests fail in isolation ... untouched cockpit-covermeter
module"), assumed to be an `os.killpg` EPERM sandbox artifact and waved off
as unrelated environmental flakiness.

## Root cause (measured, not the assumed timing race)

Not a race in the shared `drive_play_shell_pty` helper. `screens.py`'s draw
path calls `live_actor_counts(getattr(self, "ledger_path", None))`; no
product code ever sets `self.ledger_path` (deliberately pinned by
`tests/test_coverage_ledger_counts.py`), so the call always falls through to
`ledger.DEFAULT_LEDGER_PATH` — a path computed **relative to the repo
root**, not to this test's `TW_RUN_DIR` isolation. A developer sandbox with
real dev-drive history in its git-ignored, in-tree `state/ledger.jsonl`
therefore renders the *actual* live App/Human share instead of the isolated
`COV ?` both tests assert — while a clean CI checkout (no `state/` at all)
never sees it. That is why it looked "flaky": deterministic-fail in a
lived-in sandbox, deterministic-pass in CI, depending entirely on ambient
repo state neither test isolated against.

Confirmed by reproduction: copying a real, populated `state/ledger.jsonl`
into a fresh worktree reproduced both failures deterministically (100%,
4/4 serial re-runs); removing it made them pass again.

## Fix

Test-only. The bootstrap `_BOOTSTRAP` script this suite spawns in the pty
child now monkeypatches `tw2002_aiclient.ledger.DEFAULT_LEDGER_PATH` to a
path under the test's own `tmp_path` (never created, so it always reads as
absent) before `curses.wrapper(_run)` ever draws a frame — closing the one
isolation channel `TW_RUN_DIR` doesn't cover. No sleeps added; no product
code touched (`self.ledger_path`'s always-None wiring stays exactly as
`test_coverage_ledger_counts.py` pins it).

## Scope

`tests/test_cockpit_covermeter_pty.py` only.

## Out of scope

`screens.py` / `ledger.py` product wiring · other cockpit chip PTY suites ·
the `os.killpg` EPERM `RuntimeWarning` (pre-existing, documented, harmless
sandbox carve-out per `WO-TUI-KILLPG-EPERM-CURSES-PTY`).

## Accept

1. Both previously-cited tests pass reliably under `-n0`, including with a
   real, populated `state/ledger.jsonl` present in the working tree (the
   exact condition that reproduced the failure).
2. 4/4 serial re-runs green, ambient ledger present.
3. Full suite green, no regressions.

## Proof

```
# Reproduced pre-fix (ambient real ledger copied into a clean worktree):
.venv/bin/python -m pytest tests/test_cockpit_covermeter_pty.py -n0 -q
# 2 failed (COV 100% / App 690 rendered instead of COV ?)

# Post-fix, same ambient ledger still present, 4x serial:
.venv/bin/python -m pytest tests/test_cockpit_covermeter_pty.py -n0 -q
# 3 passed  (x4, stable)

# Sibling suites unaffected:
.venv/bin/python -m pytest tests/test_cockpit_covermeter.py \
  tests/test_cockpit_covermeter_wiring.py tests/test_coverage_ledger_counts.py \
  tests/test_cockpit_covermeter_pty.py tests/test_cockpit_teachband_pty.py \
  tests/test_cockpit_arm_pty.py -n0 -q
# all passed

# Full suite:
.venv/bin/python -m pytest tests/
# 7488 passed, 84 warnings
```

Live-prove: `n/a` (test-only, no product/live-path change).

## Refs

`tests/pty_helpers.py` (`drive_play_shell_pty`, shared by the five cockpit
chip PTY suites — confirmed NOT the root cause here) · `tw2002_aiclient/
ledger.py::DEFAULT_LEDGER_PATH` / `live_actor_counts` · `tw2002_aiclient/
screens.py:2150` · `tests/test_coverage_ledger_counts.py` (pins the
always-None `ledger_path` wiring this fix does not touch) ·
`WO-BUILD-MACRO-CAPTURE-PARAM-GENERALIZATION-2.md` Proof section (citation
trail).
