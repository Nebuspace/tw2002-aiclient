# WO-CANON-HEADING-CITATIONS — retire line-numbered canon citations

**Status:** DONE
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

- Convert `*.md:<line>` and `*.md:<line>-<line>` citations in `tw2002_aiclient/**/*.py`
  to heading form. All 47 resolve to real text today, so every one is a mechanical
  conversion — no judgement calls, no residuals to bank.
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
2. Every converted citation **matches** a heading in the cited canon file, under the
   match rule defined in Proof below. "Matches" is not "is equal to" — see the rule.
3. Suite green, test count unchanged (comments-only change).
4. PR + STATUS.

## Proof

Mechanical sweep asserting (a) zero remaining `\.md:[0-9]+` in product code, (b) each cited
heading matches its file under the rule below. Suite green.

### The match rule (normalisation + shape)

Two competent checkers disagreed on this WO's own PR (#113: one reported 0 problems, one
reported 2) because "the heading exists" was never defined. It is defined here.

A citation `§"CLAIM"` into `file.md` matches iff, after normalising **both** sides, `CLAIM`
is **equal to** some heading in that file **or is a prefix of one ending at a word boundary**
— the next character in the heading must be whitespace or `(`.

Normalisation, applied to both sides:

1. **Strip inline markdown** — backticks/code spans, and `*`/`_` emphasis markers.
2. **Compare dashes literally.** `-`, `--`, `–` and `—` are four distinct things; do not
   fold them. A citation must use the dash its heading uses.
3. **Collapse whitespace** — squeeze internal runs to one space, trim both ends.
4. **Compare case-sensitively.**

Headings mean ATX headings (`^#{1,6} `). Everything else is prose, not a citable section.

### Why these choices — measured on this repo, not asserted

Three checker shapes were run over the tree at `b2e586d` (clean, post-conversion) and at
`b2e586d^` (which carried exactly one known-bad citation, `loops/player.py:25`):

| checker shape | clean tree (27 cites) | tree with 1 real defect (9 cites) | verdict |
|---|---|---|---|
| equality only, dashes literal | **6 false failures** | 7 = 1 real + 6 false | too narrow — red on a correct tree |
| prefix-ok, dashes **folded** | 0 | **0 — misses the real defect** | too loose — blind to the bug it exists for |
| **prefix-ok, dashes literal** | **0** | **1 — exactly the real defect** | ✅ the rule above |

- **Prefix matching is required, not a convenience.** Six of the 27 citations on the clean
  tree deliberately cite the *stable* head of a long heading — `§"Structural rails"` for
  `# Structural rails (L4) — turn-budget, stop-loss, hazard, novelty-halt`, `§"Deterministic
  replay"` for `## Deterministic replay — one confirmed step at a time`. That is good
  practice: it is the part of the heading least likely to churn. An equality-only checker
  calls all six broken **on a tree where nothing is broken** — the third instance in this
  WO's history of *a check narrower than its claim*, after the `:91-96` range false positive
  and the two false positives during #93.
- **The boundary condition is what keeps prefix matching honest.** `§"Replay"` does *not*
  match `## Replay-safety invariants` — the next character is `-`, not whitespace or `(`.
  Without the boundary, prefix matching degrades into "starts with", which would accept
  almost anything.
- **Dashes literal, deliberately.** Folding them makes the checker silent on the one real
  defect in the table above. A checker that papers over the single bug it has already caught
  is worse than no checker.
- **Case-sensitive**, because canon headings are prose with meaningful capitalisation, and
  case-folding would let `§"the coverage meter"` pass for `## The Coverage / auto-% meter` —
  close enough to look right, wrong enough to mislead.

> **Correction (2026-07-27), recorded rather than quietly fixed.** During #113 review this
> seat reported that `loops/player.py:25` still carried an ASCII `--` against canon's em-dash
> `—`. Half right: the mismatch was real and **predated this WO** (it dates to `a7dbf22`,
> long before the conversion, so it was never conversion-introduced drift) — but it is **not**
> on `main`, because **#113 fixed it**. The tree is clean. The episode is kept because it is
> the entire empirical case for rule 2: for the whole life of that citation a dash-folding
> checker would have called it green.

## Note for whoever takes it

The verification question is **"does the cited target contain the claimed text"**, not "did the
number change" — the second is meaningless once you have changed it, and produced two false
positives when it was first attempted during #93. Whatever check ships here should ask the
first question.
