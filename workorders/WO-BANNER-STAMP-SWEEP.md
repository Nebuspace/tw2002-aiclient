# WO-BANNER-STAMP-SWEEP

**Status:** DONE · Cursor · `wo/BANNER-STAMP-SWEEP`
**Posted:** 2026-07-26 · P0 HANDOFF claimed by impl-aiclient-cursor

## Goal

Stamp DONE on `workorders/*.md` banners whose product already landed on `main` (classify chain
#31–#44, SCREENS #11, SESSION-CLASSIFY report, CODEQL #10, WEDGED #14, seed archival #45 already
SUPERSEDED).

## Scope

`workorders/` Status lines only (+ optional one-line SHA/PR cite). Do **not** rewrite bodies,
invent product, run Explore, or rewrite history.

## Out

Product code · Explore · invent · rewriting history.

## Accept

Banners no longer claim OPEN/READY/IN PROGRESS/READY FOR REVIEW/READY FOR HUB COMMIT for landed
work in the stamp map below. PR opened; suite n/a (docs-only).

### Stamp map (merge commits on `main`)

| File | Stamp |
|---|---|
| WO-LOGIN-SCROLLBACK-SEARCH-AUDIT.md | DONE · PR #31 · origin `94a29f4` |
| WO-NEVER-AUTO-ACTION-CONSUMER-AUDIT.md | DONE · PR #34 · origin `3fa3493` |
| WO-CLASSIFY-LOGIN-PASSWORD-NARROW.md | DONE · PR #36 · origin `7130871` |
| WO-CLASSIFY-PASSWORD-LENGTH-UNKNOWN.md | DONE · PR #40 · origin `60365fa` |
| WO-UNKNOWN-CLASSIFY-SEND-REFUSE-PIN.md | DONE · PR #42 · origin `ac4955b` |
| WO-CLASSIFY-API-PARITY-PLAIN-TIMEOUT.md | DONE · PR #38 · origin `29025dd` |
| WO-CLASSIFY-CHAIN-LOADBEARING-NOTE.md | DONE · PR #43 · origin `4669f4a` (premise correction also on main via #44 `7b229ae`) |
| WO-SCREENS-BADGE-DOCSTRING-STALE.md | DONE · PR #11 · origin `924cfaa` |
| WO-SESSION-CLASSIFY-AUDIT-COVERAGE.md | DONE · PR #12 · origin `a4347f0` |
| WO-CODEQL-ACTIONS-WORKFLOW-PERMS.md | DONE · PR #10 · origin `11412d4` |
| WO-CODEQL-COCKPIT-STRIP-URL-SUBSTRING.md | DONE · PR #9 · origin `de7dbeb` |
| WO-WEDGED-SEND-FENCE-STICKS.md | DONE · PR #14 · origin `8d8b1d6` |

`WO-ENSURE-MATRIX-STAMP-A5CFDDA.md` already SUPERSEDED at #45/`dfa48c4` — left as-is. Already-DONE
files (e.g. `WO-CLASSIFY-BLOCK-TITLES.md`, `WO-SCREENS-CREATE-FORM-SPLIT.md`) left alone.

## Proof

`rg 'Status.*OPEN' workorders/WO-CLASSIFY-*.md` empty or SUPERSEDED/DONE only. Every stamped SHA
verified present in `origin/main` history (`git log --oneline -1 <sha>`) before writing.
