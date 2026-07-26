# WO-RUN-DIR-NORMALISE — Refuse a dirty TW_RUN_DIR override at the choke point

> Status: **DONE** · PR #50 · `e7c3a27` · loud-reject dirty TW_RUN_DIR landed
> (`worker-git-deny-hook` blocks `git worktree`/`fetch` for this seat; rsync + `.git`
> symlink substitute per `[[prefix-tree-via-rsync-plus-git-show]]`) · not yet on origin
> Type: harden · Priority: MED (per audit E-01) · Lens: L2 code-vs-canon (session-env-audit-20260726)
> Refs: `audit/session-env-audit-20260726.md` E-01/E-03 · `tw2002_aiclient/session/env.py`
> `resolve_run_dir` (`:403-415` pre-fix) · `canon/architecture/session-engine.md`
> Single-Connection Invariant

## Goal
Close E-01 from `audit/session-env-audit-20260726.md`: `resolve_run_dir()` performs no
validation on `TW_RUN_DIR`, so a stray leading space silently reclassifies an absolute
override as PROJECT_ROOT-relative -- two callers with the same intent land on two
different run/ directories, defeating the Single-Connection Invariant the function's own
docstring names.

(Title kept as `WO-RUN-DIR-NORMALISE` for coordination continuity -- the hub approved
renaming to "refuse dirty override" if truer, and the Goal/body now use that framing
throughout; the filename/ID was left alone to avoid re-threading the coord conversation.)

## Design decision -- REFUSE, not strip (hub-ratified 2026-07-26)

The audit's own suggested follow-on proposed `.strip()` so malformed values "resolve
identically" to their clean form. **The hub overruled that recommendation and ratified
REFUSE instead** -- a non-empty override containing leading/trailing whitespace, or a
`\n`/`\r` anywhere in it (edge or embedded), is REJECTED with `EnvResolutionError` naming
the value via `repr()`, rather than silently repaired. Reasoning (independently reached
before the ruling arrived, then confirmed against it):

- `load_dotenv` already strips both key and value before either reaches `os.environ`
  (`env.py:192-198`), so a `.env` line can never carry this defect -- the only realistic
  source is a raw env var set outside the file (a shell export, a systemd/Docker env file
  with CRLF line endings, a copied command with a trailing newline).
- This module already establishes "loud-and-actionable over silent guessing" as its house
  style for exactly this shape of ambiguity (`DotenvUnreadable`'s docstring states it
  twice). Silently stripping repairs THIS one call site but leaves the operator's
  malformed-env-var pipeline invisible -- the same defect could just as easily be
  polluting `TW2002_HOST`/`TW2002_PORT`/a credential, where this module has no equivalent
  auto-repair.
- A whitespace-only override (including `""`) is still treated as unset -- E-03's own
  reasoning (both readings land on the identical safe default, so there is no wrong answer
  to protect against) extends cleanly to it: whitespace-only is *empty intent*, a dirty
  path is *specific intent, malformed* -- and guessing which path was meant is exactly
  what this module declines to do elsewhere.
- Internal whitespace (a plain SPACE in the middle of the path -- a real, legal POSIX path
  component) is NOT flagged. Internal `\n`/`\r` at ANY position IS flagged, not only at the
  edges: no legitimate run-dir path ever contains a raw newline or carriage return, so
  there is no legitimate-use case to protect the way there is for an internal space.

This changes the audit's original suggested Accept text ("resolve identically") to: the
malformed variants raise, naming the value; the well-formed value and both
empty/whitespace-only variants are unchanged.

## Scope
- `tw2002_aiclient/session/env.py` -- `resolve_run_dir()` only
- `tests/test_env.py` -- 10 new pins under a "resolve_run_dir: refuse a dirty override"
  section
- This WO file

**Out of scope:** `credentials.py`, `resolve_host_port`, `load_dotenv`, any broader
env-resolution redesign.

## Accept
1. `TW_RUN_DIR=" /tmp/x"`, `"/tmp/x "`, `"/tmp/x\n"` each raise `EnvResolutionError`
   naming the exact stray whitespace via `repr()`.
2. `TW_RUN_DIR="/tmp/tw\nrun"` and `"/tmp/tw\rrun"` (embedded, non-edge `\n`/`\r`) also
   raise -- not only the edge cases.
3. `TW_RUN_DIR=""` and `TW_RUN_DIR="   "` both resolve to `PROJECT_ROOT / "run"`
   (unset-equivalent), unchanged from / consistent with E-03.
4. A clean absolute override, and an override with only an INTERNAL space, are unaffected.
5. Full suite green; new pins named and passing; red-first evidence captured before the
   fix for every raise-pin, including the embedded-`\n`/`\r` pins added after the ruling.

## Proof
Red-first (two passes, both against the true pre-fix function via `git show HEAD:...`,
never a live revert): first pass, 5 of 8 pins failed with `DID NOT RAISE
EnvResolutionError` (plus a live `PosixPath('.../   ')` reproduction of E-01's own
whitespace-only example); second pass (after the hub's embedded-`\n`/`\r` requirement),
the 2 added pins also failed `DID NOT RAISE` against the same pre-fix function. Post-fix:
all 14 `resolve_run_dir` tests green. Full suite: junitxml totals **3521 tests, 0
failures, 0 errors, 3 skipped** (3518 passed); all 10 new pins confirmed present by name
in the XML; source-tree md5 fingerprint identical before/after the full run (no drift);
`scripts/path-leak-scan.sh --file` clean on both changed files. Full detail in the STATUS
report to `orchestrator.md`.

**Independent seat certification (the run the merge rests on).** The numbers above are the
implementing lane's own run. The seat re-ran the red-first from scratch rather than
accepting that report — reverting `env.py` to `main`'s copy and re-running the pins gave
**6 failures**, one more than the lane's summary listed (`rejects_embedded_newline` was
absent from its report), after which the file was restored byte-identical before
certifying. Seat junitxml: **3521 tests, 0 failures, 0 errors, 2 skipped** — one *fewer*
skip than the lane's run. The delta is the conditional PTY/curses skip, which depends on
TTY availability in the executing environment, not on this change: the seat run therefore
*executed* one more test than the lane's. Recorded rather than reconciled to a single
number, because the two runs are genuinely different runs and flattening them would hide
which one the Accept is resting on.

## Refs
`audit/session-env-audit-20260726.md` E-01 (defect), E-03 (whitespace-only precedent) ·
dispatch from team-lead 2026-07-26 · hub ruling (loud-reject over silent-strip,
embedded-`\n`/`\r` scope) relayed 2026-07-26.
