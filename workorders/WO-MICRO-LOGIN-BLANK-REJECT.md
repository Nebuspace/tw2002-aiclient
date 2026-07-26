# WO-MICRO-LOGIN-BLANK-REJECT

**Status:** OPEN · READY · product (`session/login.py`) · Claude Code lane · queued after fence 3A
**Posted:** 2026-07-26 · from the live-ensure diagnosis (`4f7449f`, `audit/live-ensure-stall-diagnosis-20260726.md`)

## Goal

`ensure` cannot get past `twgs.microblaster.net`'s outer login gate, because **the host does not honour
its own prompt.** Give `login.py` an honest fallback for an *explicit* rejection — without inventing a
screen class and without weakening stop-on-unknown.

## The evidence (captured, not inferred)

The gate prints `Please enter your name (ENTER for none):`. The automaton sends blank + CRLF, which is
**correct per canon**. The host replies `A login name is required.` and re-prompts. This repeats **three
times**; on the **fourth** rejection the host **goes silent** — no re-prompt at all.

`classify_screen` then sees only the rejection line, matches nothing → `unknown` → three stagnant rounds
→ `automaton_stuck:classification='unknown':step=6`.

Double-capture with an independent settle in between was **byte-identical** (`settled_reason: timeout`),
so this is a **stable screen, not a mid-paint artifact** — the settle layer is exonerated here.

**Safety note carried from the diagnosis:** the stall is **upstream of both handle and password**. No
credential is transmitted on this path, in success or failure.

## Scope

- `tw2002_aiclient/session/login.py` — the blank-name step and its rejection handling.
- Tests/fixtures for the rejection sequence.
- **NOT** `classify.py`. **NOT** a new `screen_class` (needs a separate Max GO that does not exist).

## The shape of an honest fix

The host advertises `(ENTER for none)` and then refuses it. The automaton currently has **no branch for
"my correct input was explicitly rejected"** — it just re-observes and eventually wedges.

A defensible fallback is to detect the *explicit rejection* and retry once with the profile's own handle,
since a host demanding a name is telling us plainly what it wants. **Argue it; do not assume it.**

## Constraints

- **Do not weaken stop-on-unknown.** An unrecognised screen must still halt. This adds a branch for a
  *recognised rejection*, not a licence to guess.
- **Bounded.** Whatever retry you add must be finite and must not loop against a host that keeps
  refusing — the fourth rejection arrives with **silence**, so a naive retry can hang.
- **No credential may be sent earlier than it is today.** If a fallback would move a handle or password
  earlier in the sequence, stop and say so.
- No fabricated screen classes; no new external dependencies.

## Accept

`ensure` either reaches `main_command` on micro, **or** fails with a reason that names *what the host did*
rather than `unknown`. **An honest, specific failure is an acceptable outcome** — the host may simply be
incompatible, and saying so precisely beats guessing.

## Proof

STATUS + SHA · re-run NEW (and RETURNING if a credential ever persists) against micro from an **isolated**
`TW_CONFIG_DIR` with `--run-dir` · full suite from junitxml after process exit · injection proving the new
branch is load-bearing.

## Refs

`audit/live-ensure-stall-diagnosis-20260726.md` · `session/login.py:316-328` · hub HANDOFF 2026-07-26T12:51:54Z
