# WO-CONFTEST-FAKEATTACH-CREDITS-HONESTY

**Status:** **DONE** · origin `ca8108a` · tests/fixture honesty · Claude Code · banked by hub 2026-07-26T09:18Z

> **Outcome: option (b).** The methods stay deliberately absent and both prose sites now say so.
> Option (a) — attaching the real `Session` methods — was tried and **reverted**: a class attribute
> is inherited by every subclass, so it defeats `test_a_floor_is_still_refused_when_this_session_cannot_enforce_it`,
> which asserts `not hasattr(session, "credits_snapshot")` precisely to make "this runtime cannot
> enforce a floor" a genuine condition. **The absence is load-bearing**, and the docstring had been
> instructing the one change that silently disarms a fail-closed proof.
**Posted:** 2026-07-26 · after M3 close `13f34a8`, reconcile `26dbcb1`

## Goal

`tests/conftest.py`'s `FakeAttachSession` says two contradictory things about
`observe_credits`/`credits_snapshot`, and neither is true at runtime. Make the fixture and its
prose agree with each other and with the code.

## Verified state (re-verify; do not trust this list)

Measured at tip `26dbcb1` by runtime `hasattr`, not by reading:

| where | says | true? |
|---|---|---|
| `conftest.py:128` (docstring) | they "are the REAL `Session` methods (assigned directly off the class, not reimplemented)" | **NO** — `hasattr(FakeAttachSession, 'observe_credits')` is `False`, same for `credits_snapshot` |
| `conftest.py:139` (comment) | "observe_*/snapshots deferred until Session grows those methods" | **precondition now MET** — X5 landed `Session.observe_credits` and `Session.credits_snapshot`; both `hasattr` `True` |

So the docstring describes an attachment that never happened, and the comment cites a blocker that
no longer exists. They also contradict each other, eleven lines apart.

**Note for whoever verifies:** the contradiction is invisible to `ast.get_docstring()` because line
139 is a *comment*, not part of the docstring. A whole-file grep is what surfaces it. Do not
conclude "no contradiction" from reading the docstring alone — that mistake was already made once
on this item.

## Consequence, not merely cosmetic

The docstring's stated *purpose* is real: it exists so a test driving this session through the real
dispatch / player paths exercises the same `hasattr`-guarded call sites a real `Session` would,
"rather than silently falling through the hasattr guard to a fail-closed `None`/`None`". Today the
guard **does** fall through — so any test using this fixture silently exercises the absent-credits
path while its docstring claims otherwise. X5's lane hit exactly this and subclassed the fixture in
its own file rather than touch the shared one.

## Scope

- `tests/conftest.py` only.
- No product code. No new product behavior.

## The decision to make (argue it, do not silently pick)

Either:
- **(a) Attach the real methods** — now genuinely possible since X5 landed them; makes the docstring
  true and lets future lanes use the shared fixture instead of subclassing. **But** this fixture is
  upstream of a large share of the ~3373-test suite, so the blast radius is the whole point: a test
  that currently exercises the fail-closed absent path would start exercising the real one.
- **(b) Correct both prose sites** to say the methods are deliberately absent and why, deleting the
  stale "until Session grows those methods" rationale.

**(b) is the smaller, safer change; (a) is what the docstring actually promises.** If you choose (a),
the suite result is the evidence that matters — any test whose behavior changes must be examined
individually, not waved through because the total stayed green.

## Constraints

- Do not weaken any existing pin.
- If (a) changes ANY test's behavior, stop and report rather than adjusting the test to match.
- Never write an operator-home absolute path into a committed file.

## Accept

The fixture's prose and its runtime surface agree, with no contradiction between docstring and
comment. If (a): suite green with every behavior change individually justified. If (b): the stale
rationale is gone and the absence is documented as deliberate.

## Proof

STATUS + SHA · before/after quotes · `hasattr` measurement before and after · full-suite count from
junitxml read after process exit (baseline **3373**) · explicit statement of which option was taken
and why.

## Refs

X5 STATUS (disclosed the rot; subclassed rather than edit shared fixture) · hub bank
2026-07-26T09:18Z · `tw2002_aiclient/session/session.py` (`observe_credits`, `credits_snapshot`)
