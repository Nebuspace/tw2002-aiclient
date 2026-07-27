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
| Already broken before anyone looked | 3 (`app.py` → `spectate-and-attach.md:91/:100`, blank on main) |
| Needed a human to interpret, not a number | 1 (`layout.py:183`, `×` glyph row) |

**Nothing failed in any of those cases.** A comment cannot fail, so the entire class is
invisible to CI — the same reason #98's stale capability claims survived a green suite.

Current census on `3854e70`: **46 line-numbered citations across 15 product files**, of which
**3 already resolve to blank lines**.

## Scope

- Convert `*.md:<line>` citations in `tw2002_aiclient/**/*.py` to heading form.
- Fix the 3 pre-existing broken citations by reading what they *meant* (see Constraints).
- Optional, if cheap: a check that every cited heading exists in the cited file.

## Constraints

- **No product behaviour change.** Comments and docstrings only; the suite count must not move.
- **Do not auto-convert the 3 blanks.** `app.py:378`/`:704` → `spectate-and-attach.md:100` and
  `app.py:734` → `:91` point at blank lines *on main today*. There is no text to relocate —
  read each comment and retarget honestly, or bank a follow-on if the intent is unclear.
  Guessing a plausible heading here would re-create the defect in a form that looks fixed.
- Where a citation quotes canon text, keep the quote — it is what makes the citation
  checkable at all, and it is how every break in this WO's evidence table was detected.
- Do not edit `canon/` in this WO. If a cited heading turns out to be wrong or missing,
  bank it; canon prose is Max-gated.

## Accept

1. No `*.md:<digits>` citation remains in `tw2002_aiclient/**/*.py`.
2. Every converted citation names a heading that **exists** in the cited canon file.
3. The 3 pre-existing blanks are resolved by intent, or explicitly banked with the reason.
4. Suite green, test count unchanged (comments-only change).
5. PR + STATUS.

## Proof

Mechanical sweep asserting (a) zero remaining `\.md:[0-9]+` in product code, (b) each cited
heading string is present in its file. Suite green.

## Note for whoever takes it

The verification question is **"does the cited target contain the claimed text"**, not "did the
number change" — the second is meaningless once you have changed it, and produced two false
positives when it was first attempted during #93. Whatever check ships here should ask the
first question.
