# WO-PLAY-OFFER-VISIBLE-ON-LIVE

**Status:** DONE · tip `0911d4b` · #79  
**Posted:** 2026-07-27T04:40Z · Found by live prove PR #76 / `WO-PLAY-LADDER-LIVE-PROVE`  
**Seat:** `impl-claudecode-aiclient` (Model: Fable — Play chrome)  
**Depends:** tip ≥ `9795263` · audit evidence in `audit/live-play-ladder-newchar-9795263-20260727T0430Z.md`

## Goal

Make the Play explore offer (`explore ×5 available — press E`) **visible on a live connected session** — i.e. when the LOGS band has a real daemon transcript — without erasing that transcript.

## Defect (proven live)

`app.py` sets `play.status_line` to the offer after ensure @ `main_command`.  
`screens.py` only paints `status_line` into LOGS when `has_real_tail` is false:

```text
if not has_real_tail and self.status_line and logs_inner_h > 0:
    logs_lines = [self.status_line[:logs_inner_w]]
```

Live sessions always have a populated `log_tail` after ensure → offer is written and never drawn. Unit/pty suites stub an empty tail → false green.

## Scope (owned)

- `tw2002_aiclient/screens.py` (and/or `app.py` / small cockpit helper) — a **standing** place for `status_line` that coexists with real LOGS content
- Tests that **must** fail if the offer is only visible with empty `log_tail`:
  - Fixture: status provider returns a **non-empty** `log_tail` (or equivalent that makes `newest_tail_entry` non-None)
  - Assert the offer / `status_line` text appears in the drawn output (or a dedicated composer return) while LOGS still shows transcript content
- Do **not** “fix” by making `status_line` replace the entire LOGS band when a tail exists (that erases the transcript — called out in the live audit)

## Design constraint (pick simplest that fits chrome)

Preferred: a dedicated one-line **status / offer** row in existing chrome (control strip adjacent, or a thin row above/below LOGS) that always shows `status_line` when set — LOGS keeps the daemon tail.  
Avoid inventing a third panel system.

## Out of scope

- Changing explore arm/key semantics (E→y still correct)
- Autopilot / teach A/R/T wires
- Reaping hub orphan daemons (separate hygiene)

## Accept

1. With populated `log_tail`, drawn Play chrome shows the explore-offer string (or current `status_line`) **and** at least one real log line
2. Empty-tail fallback behavior for ensure errors still works (no regression)
3. New/extended test(s) go red if offer is only rendered under empty-tail
4. Targeted pytest green; optional re-run of the live NEW-char harness after merge (secondary)

## Proof

```text
pytest tests/<offer_visible_tests> tests/test_play_explore_arm.py -q -n0
```

Live secondary (after land): same shape as LIVE-PROVE — ensure on sacrificial → offer **visible** on paint → E → y.

## Refs

- `audit/live-play-ladder-newchar-9795263-20260727T0430Z.md`
- `screens.py` ~1538–1555 · `app.py` explore offer status_line
- `workorders/WO-PLAY-LADDER-LIVE-PROVE.md`
