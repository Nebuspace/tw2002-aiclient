Goal:        Isolate why `sector_explore._run`'s first gate-check classifies
             the session as `game_select` when `tw status` on the same daemon
             concurrently reports `main_command` — halts
             `halt_not_drivable:game_select`, 0 sends — and pin the fix.
Scope:       tw2002_aiclient/session/sector_explore.py (RECONNECT_WAIT_*
             constants, `ExploreRunner.__init__`'s `guardian` kwarg, the halt
             point's guardian-tolerant wait), tw2002_aiclient/session/guardian.py
             (new public `reconnecting` property), tw2002_aiclient/session/daemon.py
             (wires `guardian=guardian` into the `ExploreRunner` construction).
             tests/test_explore_guardian_reconnect_tolerance.py (new),
             tests/test_guardian.py (new pin for the property).
Constraints: This was THE linchpin blocking chains-discovery, credit-doubling,
             and both purchase axes from the live-drive research. Diagnose
             first (mechanism cited, not guessed), fix only once the
             mechanism was confirmed by grep (zero non-guardian module read
             `_reconnect_in_flight` before this WO). Tolerance window only —
             never a substitute for the guardian's own reconnect_exhausted
             handling; a burst that never clears still halts, bounded by
             RECONNECT_WAIT_TIMEOUT_S.
Accept:      Root cause: `ExploreRunner._run` had zero coordination with
             `SessionGuardian`'s D9 reconnect+login-replay burst — a burst
             mid-replay legitimately passes through `game_select` on a
             multi-game BBS before picking a game letter again, and explore's
             gate-check, reading the live screen with no awareness of the
             burst, misclassified that transient artifact as a permanent
             halt. `tw explore start` now continues past a guardian-burst
             screen instead of halting on it; a regression test pins both
             directions (tolerates mid-burst, still halts once the burst
             clears or times out, unaffected default with no guardian).
Proof:       .venv/bin/python -m pytest tests/test_explore_guardian_reconnect_tolerance.py
             tests/test_guardian.py tests/test_sector_explore.py
             tests/test_explore_halt_reason_class.py -n0 -q → all green.
             Live re-verify on scout_academy (crawl_sacrificial=true):
             `tw explore start --dock-new-ports` → outcome=completed,
             distinct_sectors=5, sends_issued=8 (was 0/halted before the
             fix). `tw chains` then returns 14 real discovered trade loops
             (was `no_tradeable_hops` before).
Refs:        canon/research/autopilot-live-drive-findings-2026-08-08.md (Axis 5),
             tw2002_aiclient/session/guardian.py, PR #549.
