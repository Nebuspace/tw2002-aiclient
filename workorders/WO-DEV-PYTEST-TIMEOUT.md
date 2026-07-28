# WO-DEV-PYTEST-TIMEOUT — Global pytest hang → named failure

**Status:** IN PROGRESS · EXECUTE · MED · Cursor-class · impl-aiclient-cursor  
**Posted:** 2026-07-28T01:14Z · hub  
**Seat:** impl-aiclient-cursor  
**Max gate:** dependency OK in principle (Max 2026-07-27 evening — recorded on CC #127 STATUS); scheduling only  

## Goal

Add `pytest-timeout` so a hung test becomes a **named failure** instead of an infinite suite hang. Motivating evidence: #127 budget-guard mutation took **21.6s** on a small ring; on a larger graph the same class of regression does not fail — it hangs forever. Repo already runs PTY / daemon / subprocess tests that can wedge.

## Scope

- `requirements-dev.txt` — add `pytest-timeout` (pin a recent stable lower bound)
- `pytest.ini` — generous **global** default timeout (suggest 60–120s; document rationale in commit/WO)
- Per-test / per-mark overrides only where a test is legitimately slower than the default (cite why in STATUS)
- Optional: one tiny self-test or docs note that timeout fires (do not add a flaky forever-sleep to CI without a mark that is deselectable)

## Constraints

- Dev/test dependency only — **not** a runtime dependency of the product package
- Do not change product code
- Do not weaken existing suite honesty (collect hygiene / junitxml)
- Do not attach to `wo/CHAIN-DETECT-WIRE` / #128
- Prefer method=`thread` or the plugin default that works with `pytest-xdist` (`-n auto`); if xdist interaction is broken, STATUS with evidence and propose fix — do not silently ship a no-op

## Accept

1. `pytest-timeout` listed in `requirements-dev.txt`; installable via existing venv install path.
2. Global timeout configured in `pytest.ini` (or equivalent pytest config the suite already loads).
3. Suite still green on a normal run (junitxml counts in STATUS).
4. Demonstrated: a deliberately slow/hung *local* probe (not necessarily committed) is killed/fails with a timeout message — describe the probe in STATUS.
5. PR + STATUS + SHA.

## Proof

- Offline suite green after install.
- live-prove **n/a** — CI/dev-tooling only; no login/ensure/classify/play/session path.

## Refs

- CC #127 STATUS 2026-07-28T00:52:15Z (mutation hang evidence + Max permission)
- Hub bank note on Accept #127
