# WO-RUN-DIR-NORMALISE — Refuse whitespace-polluted TW_RUN_DIR at the choke point

> Status: **BUILT — awaiting hub commit** 2026-07-26 · built in an isolated worker tree
> (`worker-git-deny-hook` blocks `git worktree`/`fetch` for this seat; rsync + `.git`
> symlink substitute per `[[prefix-tree-via-rsync-plus-git-show]]`) · not yet on origin
> Type: harden · Priority: MED (per audit E-01) · Lens: L2 code-vs-canon (session-env-audit-20260726)
> Refs: `audit/session-env-audit-20260726.md` E-01/E-03 · `tw2002_aiclient/session/env.py`
> `resolve_run_dir` (`:403-415` pre-fix) · `canon/architecture/session-engine.md`
> Single-Connection Invariant

## Goal
Close E-01 from `audit/session-env-audit-20260726.md`: `resolve_run_dir()` performs no
whitespace normalisation on `TW_RUN_DIR`, so a stray leading space silently reclassifies
an absolute override as PROJECT_ROOT-relative -- two callers with the same intent land on
two different run/ directories, defeating the Single-Connection Invariant the function's
own docstring names.

## Design decision -- REFUSE, not strip (deviates from the audit's suggested fix)

The audit's own suggested follow-on proposed `.strip()` so all four of `/x`, ` /x`, `/x `,
`/x\n` "resolve identically." Implemented instead: a non-empty override that differs from
its own `.strip()` is REJECTED with `EnvResolutionError` naming the value via `repr()`,
rather than silently repaired. Reasoning:

- `load_dotenv` already strips both key and value before either reaches `os.environ`
  (`env.py:192-198`), so a `.env` line can never carry this defect -- the only realistic
  source is a raw env var set outside the file (a shell export, a systemd/Docker env
  file, a copied command with a trailing newline). In every one of those cases the
  whitespace is almost certainly an artifact of *how* the value was set, not intended
  path content.
- This module already establishes "loud-and-actionable over silent guessing" as its house
  style for exactly this shape of ambiguity (`DotenvUnreadable`'s docstring states it
  twice: refuses to treat an unreadable file as absent; "a new failure defaults to
  loud-and-actionable, never to an escape"). Silently stripping repairs THIS one call
  site but leaves the operator's malformed-env-var pipeline invisible -- the same defect
  could just as easily be polluting `TW2002_HOST`/`TW2002_PORT`/a credential, where this
  module has no equivalent auto-repair.
- A whitespace-only override (including `""`) is still treated as unset -- E-03's own
  reasoning (both readings land on the identical safe default, so there is no wrong
  answer to protect against) extends cleanly to it.
- Internal whitespace (a path with a space in the middle -- a real, legal POSIX path
  component) is NOT flagged; only leading/trailing whitespace triggers the check, pinned
  by its own regression test.

This changes the audit's suggested Accept text ("resolve identically") to: the three
malformed absolute-path variants raise, naming the value; the well-formed value and both
empty/whitespace-only variants are unchanged. **Flagged for hub review** -- the dispatch
explicitly invited this reconsideration and was not certain the strip recommendation was
right.

## Scope
- `tw2002_aiclient/session/env.py` -- `resolve_run_dir()` only
- `tests/test_env.py` -- 8 new pins under a new "resolve_run_dir whitespace
  normalisation" section
- This WO file

**Out of scope:** `credentials.py`, `resolve_host_port`, `load_dotenv`, any broader
env-resolution redesign.

## Accept
1. `TW_RUN_DIR=" /tmp/x"`, `"/tmp/x "`, `"/tmp/x\n"` each raise `EnvResolutionError`
   naming the exact stray whitespace via `repr()`.
2. `TW_RUN_DIR=""` and `TW_RUN_DIR="   "` both resolve to `PROJECT_ROOT / "run"`
   (unset-equivalent), unchanged from / consistent with E-03.
3. A clean absolute override, and an override with only INTERNAL whitespace, are
   unaffected.
4. Full suite green; new pins named and passing; red-first evidence captured before the
   fix.

## Proof
Red-first: 5 of 8 new pins in `tests/test_env.py` failed against the pre-fix function
(`DID NOT RAISE` / a live `PosixPath('.../   ')` reproduction of E-01's own example),
captured verbatim in the STATUS report. Post-fix: all 12 `resolve_run_dir` tests green;
full-suite junitxml totals + before/after tree fingerprint also in the STATUS report to
`orchestrator.md`.

## Refs
`audit/session-env-audit-20260726.md` E-01 (defect), E-03 (whitespace-only precedent) ·
dispatch from team-lead 2026-07-26.
