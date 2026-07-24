# WO-P3-DOC-GAP-GLYPH-TONES — Close tip-`2a2d65c` visual-language gaps

> Status: **EXECUTE DONE** 2026-07-24 · docs only  
> Seat: implementer · **No product code**

## Goal

Land three DOC-GAPs in `canon/surfaces/visual-language.md` so canon matches shipped
cockpit tip `2a2d65c` (glyph `×`, strip data-tone, too_small gate tone).

## Shipped (canon)

1. Glyph table — `×` NO-SWAP row (family of `·` / `—`); cited by `too_small` string.
2. Row-1 profile strip — **data / `A_NORMAL`** ("cyan is chrome, never data").
3. `too_small` refusal — **info cyan+bold** (gate statement, not warn/danger).

`trainer-cockpit.md` untouched (no conflicting restatement requiring a cross-cite).

## Proof cites (shipped code)

| DOC-GAP | Code |
|---|---|
| `×` in refuse copy | `tw2002_aiclient/cockpit/layout.py` ≈97–102 |
| strip `A_NORMAL` | `tw2002_aiclient/screens.py` ≈381–387 |
| refuse cyan+bold | `tw2002_aiclient/screens.py` ≈363–364 (`_outer_attr` ≈352–357) |
