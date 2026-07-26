# Honesty audit — `tw2002_aiclient/session/env.py`

**Seat:** `impl-claudecode-aiclient` · **Tip audited:** `origin/main` `dfa48c4` · **Mode:** READ-ONLY, no product change
**Companion to:** `audit/session-classify-audit-coverage-20260726.md`
**Method:** every finding below was produced by **executing** the function against a constructed input, not by reading it. Where a probe found nothing, that is stated too.

---

## Summary

`env.py` is, on the whole, one of the more honest modules in the tree. The `DotenvUnreadable` / absent-vs-unreadable work has already been done deliberately and is documented with its own history. **The precedence surfaces the WO named came back clean under probing.** The one real defect is elsewhere — in `resolve_run_dir`, and it touches the Single-Connection Invariant.

| # | Surface | Severity | Status |
|---|---|---|---|
| E-01 | `resolve_run_dir` does not normalise whitespace — two callers with the same intent get different sockets | **MED** | defect |
| E-02 | Invalid `TW2002_PORT` message points at a `.env` the process could not read | **LOW** | wording |
| E-03 | `TW_RUN_DIR=""` is indistinguishable from unset | **LOW** | judgement, probably fine |
| — | `.env` absent-vs-unreadable honesty | — | **probed, clean** |
| — | held-`.env` precedence (tiers 1–2 settle → hold; don't → raise) | — | **probed, clean** |

---

## E-01 · MED · `resolve_run_dir` splits one run-dir into many — `env.py:403-415`

`resolve_run_dir` accepts `TW_RUN_DIR` with no normalisation:

```python
override = os.environ.get(RUN_DIR_VAR)
if not override:
    return PROJECT_ROOT / "run"
p = Path(override)
return p if p.is_absolute() else (PROJECT_ROOT / p)
```

`if not override` rejects `""` but nothing else. Measured:

```
TW_RUN_DIR='/tmp/twrun'    -> socket '/tmp/twrun/twd.sock'
TW_RUN_DIR=' /tmp/twrun'   -> socket '<PROJECT_ROOT>/ /tmp/twrun/twd.sock'   ← leading space
TW_RUN_DIR='/tmp/twrun '   -> socket '/tmp/twrun /twd.sock'                  ← trailing space
TW_RUN_DIR='/tmp/twrun\n'  -> socket '/tmp/twrun\n/twd.sock'                 ← trailing newline
TW_RUN_DIR='   '           -> socket '<PROJECT_ROOT>/   /twd.sock'
```

**A leading space silently converts an absolute path into a relative one**, because `Path(" /tmp/twrun").is_absolute()` is `False`. The result is joined under `PROJECT_ROOT`, producing a socket in a directory whose name begins with a space.

**Why this is MED rather than cosmetic.** The module's own docstring states the purpose: *"`tw`/`twd` invoked from any directory resolve to the same `run/` home, **per the Single-Connection Invariant**."* That invariant is enforced by **path agreement** — one socket, one pidfile, one daemon. Two callers that believe they share a run-dir but differ by an invisible character get **two daemons and two sockets**, and neither can see the other's control lock. `tw status` would report nothing running while a daemon holds the connection.

The realistic source is not exotic: a `.env` line, a shell export, or a copied command with a trailing newline or stray space. **The failure is silent and the difference is invisible in most terminals.**

**Suggested follow-on:** `WO-RUN-DIR-NORMALISE` — strip surrounding whitespace before the `is_absolute()` test, and treat a whitespace-only override as unset (with the same fallback as `""`). A pin should assert `resolve_run_dir()` is identical for `"/x"`, `" /x"`, `"/x "` and `"/x\n"`.

---

## E-02 · LOW · an error names a file it could not read — `env.py:~360`

When `TW2002_PORT` is non-integer, the raise is immediate and correct:

```
TW2002_PORT is set to 'not-an-int', which is not a valid integer port
  -- fix it in the environment or .env.
```

Probed with an unreadable `.env` present: the message is unchanged, and the held `DotenvUnreadable` is never mentioned. **The tier ordering is right** — a broken tier-2 var should be fixed before anything else, and the `.env` genuinely could not have helped.

**The wording is what is off.** *"or .env"* directs the operator to edit a file this process has just failed to read, without saying so. They may edit a `.env` the daemon still cannot open and see no change.

**Suggested follow-on (docs/wording only):** when `dotenv_failure is not None`, drop the *"or .env"* clause or append *"(note: the `.env` overlay could not be read — see below)"*. Low severity: the primary instruction is correct and actionable.

---

## E-03 · LOW · `TW_RUN_DIR=""` is silently the default — `env.py:410`

An empty override falls through to `PROJECT_ROOT / "run"` with no signal. This is defensible — empty-equals-unset is a common shell convention, and `export TW_RUN_DIR=` reads as "clear it".

**Flagged only for the record**, because it is the same shape as `{}`-versus-unreadable that this module took such care over elsewhere: an empty value is a *claim* that could mean "unset" or "set to nothing by mistake". Unlike the `.env` case, both readings lead to the same safe place, so there is no wrong answer to protect against. **No follow-on recommended.**

---

## Probed and clean — stated so the absence of a finding is not mistaken for absence of a check

**`.env` absent vs unreadable.** `load_dotenv` opens the file rather than calling `Path.exists()`, and its docstring records both directions of the trap that motivated the change. Nothing to add — the honesty work is already done and correctly reasoned.

**Held-`.env` precedence.** Two probes:

- host unresolved, port unresolved, `.env` unreadable → **raises**, naming the file and the three ways out. Correct: the unread file was the next tier.
- host resolved from env, port unresolved, `.env` unreadable → **raises**. Correct: tiers 1–2 did *not* settle it; the `.env` would have supplied the port.

The asymmetry the docstring argues for — hold if tiers 1–2 settled, raise if they did not — **is what the code actually does.**

**Secret discipline.** `DotenvUnreadable.reason` is bounded and never carries file content; the docstring explains that a `.env` may legitimately hold `TW2002_PASSWORD_<PROFILE>`, so decode failures render as a type name plus integer offsets rather than `str(exc)` or `exc.object`. **This is the correct treatment and matches `canon/doctrine/secrets-and-credentials.md`.**

---

## Note on method

Findings E-01 and E-02 came from executing the functions with adversarial inputs; the two "clean" surfaces came from the same treatment producing nothing. **A surface reported clean here means a probe was run and returned the expected answer** — not that the code was read and looked reasonable. The distinction matters because the most careful-looking module in a tree is exactly where reading substitutes for testing.
