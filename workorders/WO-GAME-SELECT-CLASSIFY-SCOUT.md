# WO-GAME-SELECT-CLASSIFY-SCOUT

**Status:** OPEN · Cursor preferred · scout only (UNVERIFIED)  
**Posted:** 2026-07-26 · banked from CC 02:57:58Z

## Goal

Settle whether archive corpus "game-select screens classify as `menu`" is real on a **rendered 80×25 grid**, or only a blind corpus probe / scrolled-off banner.

## Scope

- Replay harness: real `TelnetHandler → TerminalScreen`, logs opened `newline=""`
- Classify at **settled** frames carrying the Selection prompt
- Report: class distribution **and** whether TWGS startup banner is still on the rendered grid at that moment
- Scout note under `workorders/` (update this file or sibling) — **no product classify change** unless hub GO mid-flight

## Constraints

- Corpus may contain **real player handles** — trim before any tracked fixture
- Do not WO a "fix" from this alone — report distinguishes "conjunction broken" vs "banner scrolled off"
- Stay off `protocol.py` (CC X1)

## Accept

One-page scout with both answers (class distribution · banner-on-grid yes/no) + recommendation; STATUS.

## Proof

STATUS (docs artifact) · cite method.

## Refs

CC 2026-07-26T02:57:58Z · hub ACK scout-only · screen-understanding game_select exclusivity
