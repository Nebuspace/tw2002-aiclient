# WO-RULE-ENGINE-WIRE — wire guarded-rule kernel to store + run-loop choke-point

**Status:** READY · automation frontier (follow-on #219)
**Seat:** `impl-claudecode-aiclient`
**Branch:** `wo/RULE-ENGINE-WIRE`
**Depends:** `main` ≥ `a9e0dd0` (`rule_engine.py` kernel on main)

## Goal

Make `tw2002_aiclient.rule_engine` reachable from the taught-behavior path: load
approved rules through the strict parser, select a macro name for a recognized
screen + facts, and refuse execution when the external arm input is false —
**re-read at every send choke-point**, not once at entry.

Kernel DONE ≠ reflex layer live until this lands.

## Scope

- Rule **store/load** path that calls the kernel's **`parse_rule` / strict schema**
  (no lenient store twin; test must go red if any load path bypasses parser).
- Wire selection into the existing taught run path:
  `arm-confirm → adapters.autoloop_start → session/autoloop.py → replay_loop`
  (trace and preserve; do not invent a parallel player).
- **Arm gate:** required external input, **no default** (not an internal
  self-check). Run-loop / caller owns arm state; choke-point re-reads it every
  boundary (mirror `floor` ownership: `autoloop` decides, `player` checks each
  step).
- Focused tests + pins proving parser unity, arm re-read, and selection reachability.

## Constraints

- **`approved` ≠ `armed`.** Kernel filters drafts; arm is outside the kernel.
- Do **not** add `force=True`-style bypass or a self-granted arm flag on
  `LoopPlayer` (canon forbids).
- **`NEVER_AUTO_ACTION_CLASSES` stays unconditional** at player boundaries.
  Approved rules that reach buy/sell prompts will halt on `never_auto_action:*`
  — **disclose as deliberate in STATUS**, not a wire defect.
- Opening §A.2 exemption (auto action on money prompts) is **out of scope** and
  **Max-gated** — separate WO if ever pursued.
- No new external dependencies.
- No test-hygiene-only churn unrelated to the wire.

## Accept

1. Persisted rules load only through the same strict parser as unit tests
   (bypass test included).
2. At least one product path calls `select_rule` (or equivalent) with real
   screen class + facts and receives macro name or typed STOP.
3. When arm input is false at choke-point, **no send** occurs (prove by test,
   not log assertion).
4. Disarm mid-run is observed **within one boundary** (re-read, not entry-only).
5. Full offline `suite` green; focused wire tests with mutation where feasible.
6. STATUS documents inert `never_auto_action` landing explicitly.

## Proof

- Focused tests: parser bypass guard · arm false → zero sends · arm flip mid-run
  · rule selection happy path.
- Full offline `suite`.
- Live-prove: `n/a` unless this slice adds a new live-touch send path beyond
  existing autoloop chain (expected: `n/a` with reason if unchanged transport).

## Refs

- `workorders/WO-GUARDED-RULE-KERNEL.md` (#219)
- `canon/architecture/rule-macro-engine.md`
- `canon/architecture/app-autopilot-model.md` (arm re-read at choke-point)
- `tw2002_aiclient/loops/player.py` (`floor` precedent; no arm predicate today)
- CC contract objection 2026-07-29T12:58Z
