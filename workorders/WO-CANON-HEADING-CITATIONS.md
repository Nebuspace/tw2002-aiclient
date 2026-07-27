# WO-CANON-HEADING-CITATIONS — retire line-numbered canon citations

**Status:** OPEN · READY
**Posted:** 2026-07-27 · authored by `impl-claudecode-aiclient` at hub request after the #109 citation incident
**Seat:** open — mechanical, no product behaviour change
**Depends:** `main` ≥ `3854e70` (#109 chrome-orphan retire + its citation repair)
**Refs:** #93 (citation repair inside a canon PR) · #98 (stale capability claims) · #109 STOP-THE-LINE 2026-07-27T19:18:50Z

## Goal

Replace line-numbered canon citations in product code (`canon/…/foo.md:123`) with
**section-heading citations** (`canon/…/foo.md` §"The coverage / auto-% meter"), so an
ordinary canon edit stops silently invalidating comments across the tree.

## Why — measured, not asserted

Line numbers are a decaying pointer. One ordinary canon edit broke most of them in a day:

| event | measurement |
|---|---|
| #109 (a routine SoT-honesty edit to 5 canon files) | **18 of 25** citations into those files broke |
| Several landed on **blank lines** | `panic.py` → `mode-line…:234`, three sites → `visual-language.md:302` |
| One landed on the **wrong semantic row** | `armconfirm.py:71` cited the `danger` tone row, would have read `warn` |
| Survivors survived by **luck** | 7 unaffected only because edits happened *below* them |
| Needed a human to interpret, not a number | 1 (`layout.py:183`, `×` glyph row — genuinely blank, fixed in #109 as `:154`) |

**Nothing failed in any of those cases.** A comment cannot fail, so the entire class is
invisible to CI — the same reason #98's stale capability claims survived a green suite.

Current census on `3854e70`: **47 line-numbered citations across 15 product files**, and
**all 47 currently resolve to real text** — see the correction note below.

> **Correction (2026-07-27).** An earlier version of this WO claimed 3 citations
> (`app.py` → `spectate-and-attach.md:91`/`:100`) were already broken. **That was wrong.**
> Those are *range* citations (`:91-96`, `:100-102`) whose first line is ordinary markdown
> spacing; the ranges carry exactly the text the comments claim. The error was in the
> checking script, which asked "is line N blank?" when the claim was "does the cited range
> contain the claimed text" — a check narrower than its claim, which is the very defect this
> WO exists to make impossible. Recorded rather than silently edited, because the next
> person writing a citation checker will reach for the same shortcut.

## Scope

- Convert `*.md:<line>` citations in `tw2002_aiclient/**/*.py` to heading form.
- Fix the 3 pre-existing broken citations by reading what they *meant* (see Constraints).
- Optional, if cheap: a check that every cited heading exists in the cited file.

## Constraints

- **No product behaviour change.** Comments and docstrings only; the suite count must not move.
- **Any checker written for this WO must be range-aware.** Citations come in both
  `file.md:123` and `file.md:123-456` forms. A checker that inspects only the first line of a
  range reports false breakage (it did — see the correction above). Ask whether the cited
  *span* contains the claimed text.
- Where a citation quotes canon text, keep the quote — it is what makes the citation
  checkable at all, and it is how every break in this WO's evidence table was detected.
- Do not edit `canon/` in this WO. If a cited heading turns out to be wrong or missing,
  bank it; canon prose is Max-gated.

## Accept

1. No `*.md:<digits>` citation remains in `tw2002_aiclient/**/*.py` (single-line or range).
2. Every converted citation names a heading that **exists** in the cited canon file.
3. Suite green, test count unchanged (comments-only change).
4. PR + STATUS.

## Proof

Mechanical sweep asserting (a) zero remaining `\.md:[0-9]+` in product code, (b) each cited
heading string is present in its file. Suite green.

## Note for whoever takes it

The verification question is **"does the cited target contain the claimed text"**, not "did the
number change" — the second is meaningless once you have changed it, and produced two false
positives when it was first attempted during #93. Whatever check ships here should ask the
first question.
