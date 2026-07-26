# WO-AUDIT-SESSION-ENV

**Status:** **DONE** · report on `main` · read-only audit, no product change
**Posted:** 2026-07-26 · orchestrator HANDOFF 22:53:39Z · companion from the classify-coverage report
**Seat:** `impl-claudecode-aiclient` · **Tip audited:** `origin/main` `dfa48c4`

## Goal

READ-ONLY honesty audit of `tw2002_aiclient/session/env.py` — name the defects with `file:line`, assign severity, and propose follow-on WO titles. **No product fixes in this WO.**

## Scope

- `audit/session-env-audit-20260726.md` — the report
- this WO file
- **Out:** `credentials.py` (separate, Cipher-gated) · Explore/M4 · invent · drive-by refactors

## Result

| # | Surface | Severity | Follow-on |
|---|---|---|---|
| E-01 | `resolve_run_dir` does not normalise whitespace — a leading space turns an absolute override relative, so two callers with the same intent resolve **different sockets**, defeating the Single-Connection Invariant by path disagreement | **MED** | `WO-RUN-DIR-NORMALISE` |
| E-02 | Invalid `TW2002_PORT` message says "fix it in the environment or .env" while the `.env` is one the process failed to read | **LOW** | wording-only |
| E-03 | `TW_RUN_DIR=""` indistinguishable from unset | **LOW** | none recommended |

**Probed and clean, stated explicitly:** `.env` absent-vs-unreadable honesty · the held-`.env` precedence asymmetry (hold if tiers 1–2 settled, raise if not) · `DotenvUnreadable`'s secret discipline.

## Accept

1. ✅ Report on `main` citing the audited tip SHA.
2. ✅ The override-precedence and `DotenvUnreadable` honesty surfaces named — both **probed by execution** and reported clean rather than assumed.
3. ✅ Defects carry `file:line`, severity, and suggested follow-on titles.
4. ✅ No product code touched.

## Proof

`audit/session-env-audit-20260726.md` on `origin/main`; every finding reproduced by executing the function against a constructed input, with the measured output quoted in the report.

## Note

The two surfaces the HANDOFF named came back **clean**; the one real defect was in `resolve_run_dir`, which the HANDOFF did not name. Recorded because a WO that finds its defect somewhere other than where it looked is worth being able to see later — and because "clean" here means a probe ran, not that the code read well.
