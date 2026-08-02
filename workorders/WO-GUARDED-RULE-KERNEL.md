# WO-GUARDED-RULE-KERNEL — taught-rule eligibility and deterministic selection

**Status:** DONE · origin `a9e0dd0` (#219) · tip-honesty stamp 2026-08-02 (product on main; banner was stale READY)
**Seat:** `impl-claudecode-aiclient`
**Branch:** `wo/GUARDED-RULE-KERNEL`
**Depends:** state parser LIVE · macro recorder/loader/player LIVE · arm-confirm LIVE
**Canon:** `canon/architecture/rule-macro-engine.md`

## Goal

Build the missing pure decision kernel between recognized state and taught macro
replay:

`screen_match + typed guards + human approval → one named macro, or typed STOP`.

This is the first unbuilt automation dependency. It is not a test-hygiene WO and
it does not send a keystroke.

## Scope

- New dependency-neutral product module under `tw2002_aiclient/` for:
  - the canonical guarded-rule schema
  - strict document validation / round-trip serialization
  - pure guard evaluation over a supplied facts mapping
  - deterministic selection over a supplied screen class and rules
- Focused tests for the new product behavior.

The implementer chooses the final module/test names after checking current
package conventions. No existing product module should need editing in this
slice.

## Required schema

Each rule carries:

- stable rule id
- `screen_match`
- typed `guards`
- named macro target (`do`)
- integer `priority`
- `scope: one-shot | repeating`
- `approved: bool`

Each guard names a fact, comparison/operator, expected value where applicable,
failure posture (`ineligible` or `stop`), and a typed STOP reason when its
posture is `stop`.

## Constraints

- Pure logic only: no curses, socket, daemon, control-lock, filesystem policy,
  macro execution, or live send.
- No AI/model call and no expected-value action scoring.
- Draft/unapproved rules are inert.
- Unknown/missing guard facts fail closed; never coerce missing to zero/false.
- A STOP guard outranks a fireable survivor.
- No matching approved rule returns typed STOP/escalation, never a fallback
  macro.
- Competing eligible rules must have a deterministic winner. Do not silently
  use input order. Reject an ambiguous equal-priority document or return typed
  ambiguity STOP.
- Serialization must round-trip without silently dropping fields.
- No new dependency.

## Build wave

1. **Kernel lane:** schema, validation, guard evaluator, selector.
2. **Proof lane:** focused truth-table tests plus mutation controls.
3. **Adversarial review:** prove drafts never fire, unknown fails closed,
   STOP dominates, ties cannot depend on input order, and no send/import
   boundary entered.

Workers do not mutate git. Lead integrates, commits explicit paths, fetches
before push, and reports STATUS with SHA and proof.

## Accept

1. Approved matching rule + passing guards selects its named macro.
2. Unapproved matching rule is treated as absent and cannot win by priority.
3. Missing/unknown required fact cannot produce a macro selection.
4. A `stop` guard returns its typed reason and no macro.
5. No matching approved rule returns a typed no-match STOP.
6. Selection is invariant under input permutation.
7. Strict parse/serialize/parse round-trip preserves the complete document.
8. Focused tests and full offline `suite` pass.
9. Product diff is the new kernel only; existing modules remain unchanged.

## Proof

- Focused tests with mutation controls for approval, unknown fact, STOP
  dominance, priority, and input permutation.
- Fresh-interpreter import of the new module.
- Full offline `suite`.
- Live-prove: `n/a` — this slice is pure, dependency-neutral logic and cannot
  reach transport or runtime state.

## Follow-on (not this WO)

Wire this kernel to the existing macro store/player and external human arm;
then prove re-validation and STOP-on-unknown through the live App run-loop.
