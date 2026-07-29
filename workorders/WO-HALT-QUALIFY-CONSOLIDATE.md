# WO-HALT-QUALIFY-CONSOLIDATE

## Goal

Remove the independent `_qualify` implementations in LoopPlayer and sector
explore by giving halt-reason encoding and parsing one dependency-neutral source
of truth. Runtime halt behavior and emitted strings must remain unchanged.

## Scope

Owned implementation paths:

- `tw2002_aiclient/halt_reasons.py` (new shared primitive)
- `tw2002_aiclient/loops/player.py`
- `tw2002_aiclient/session/sector_explore.py`
- focused halt-reason tests under `tests/`

Branch owner: `impl-claudecode-aiclient` after HANDOFF.

## Constraints

- Preserve the exact wire/display shape: `<code>:<detail>`.
- Preserve `halt_reason_code` behavior for empty, non-string, unqualified, and
  multi-colon values.
- Do not change halt classification, gating, send behavior, reason constants,
  stop-banner presentation, or public CLI behavior.
- Do not make `sector_explore` import `loops.player` merely to reach the helper.
- Keep the shared module dependency-neutral; it must not import session, loops,
  cockpit, or adapter modules.
- Keep compatibility imports in `loops.player` if existing callers/tests import
  `QUALIFIER_SEP`, `_qualify`, or `halt_reason_code` there.
- No new dependency.

## Build wave

Use disjoint lanes:

1. **Implementation lane:** add the shared primitive and re-export/import it from
   both producers without changing behavior.
2. **Proof lane:** update focused tests and independently scan all qualification
   and parser call sites for drift or compatibility breakage.
3. **Adversarial review:** verify import direction, exact strings, first-colon
   parsing, and that the AST comparison guard still derives both qualifiable
   constants.

Workers do not mutate git. The lead integrates, runs gates, commits explicit
paths, fetches before push, and reports STATUS with SHA and proof.

## Accept

1. Exactly one implementation constructs qualified halt reasons.
2. Exactly one implementation parses the base code from a qualified reason.
3. LoopPlayer and sector explore emit byte-identical reasons for their existing
   inputs.
4. Existing imports from `tw2002_aiclient.loops.player` remain compatible.
5. The focused halt-reason suites and full offline suite pass.
6. No unrelated production or test changes.

## Proof

- Focused:
  - `pytest -q tests/test_player_halt_reason_class.py`
  - `pytest -q tests/test_explore_halt_reason_class.py`
  - `pytest -q tests/test_halt_reason_comparison_guard.py`
  - `pytest -q tests/test_never_auto_action.py`
- Full offline `suite`.
- Mutation/control proof must cover separator drift and first-colon parsing.
- Live: **DEFERRED → Cursor** after suite green. Because this touches player and
  session code, the hub merge ritual requires the standard ≥3-server diversity
  prove unless the hub documents a rule-backed exception.

## References

- `canon/doctrine/action-safety-guards.md`
- `canon/architecture/control-and-escalation.md`
- `workorders/WO-HALT-REASON-NE-SWEEP.md`
- `tests/test_halt_reason_comparison_guard.py`
