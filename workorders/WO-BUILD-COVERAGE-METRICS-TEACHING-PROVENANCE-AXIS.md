Goal:        Build the teaching-provenance coverage axis (rule origin: human vs
             ai-drafted-and-approved) that `canon/engine/coverage-metrics.md`
             (lines 165-167) names as "still prescribed, not built here".
Scope:       tw2002_aiclient coach_engine rule store — additive `origin` field
             (`human` | `ai-approved`); coverage_metrics computation — third
             axis alongside the existing app/human split; tests for both.
Constraints: Additive only — existing rule-store entries without an `origin`
             field must keep loading and count as a distinct `unknown`/legacy
             bucket (never silently default into either real origin). Do not
             touch the app/human send-attribution axis
             (WO-BUILD-COVERAGE-METRICS-COMPUTATION's lane) or the AI-teacher
             response path (WO-BUILD-AI-TEACHER-LLM-ESCALATION's lane). If the
             LLM-escalation WO lands first, consume its provenance tagging
             rather than inventing a parallel one.
Accept:      Rules persist and reload an `origin` value; coverage metrics
             report per-origin coverage as a third axis; a store predating this
             field loads unchanged with those rules bucketed as legacy/unknown;
             existing coverage numbers for the other two axes are unchanged
             (pinned by test).
Proof:       Targeted pytest for the new tests + full suite diffed against
             clean main (pre-existing failures reproduce identically on main).
             live-prove: n/a (offline metrics).
Refs:        canon/engine/coverage-metrics.md:165-167 · queue-aiclient.md
             Cycle-46 row (verified-against 2026-08-08).
