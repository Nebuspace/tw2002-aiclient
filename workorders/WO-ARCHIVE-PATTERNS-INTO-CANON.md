# WO-ARCHIVE-PATTERNS-INTO-CANON

**Status: DONE** — tip committed this session.

---

## Goal

Deep-mine `archive/pre-rebirth-2026-07-23/code/twclient/` for algorithms, data models, and
structural patterns that are useful for the upcoming greenfield build. Extract them as portable
prose + pseudocode into a new OKF Reference concept in `canon/research/`. No archive code is
restored to root; archive is reference only.

## Scope

- **New:** `canon/research/archive-port-patterns.md` (OKF Reference, type Reference)
- **New:** `canon/research/` directory
- **Updated:** `canon/index.md` — Research section added
- **Updated:** `canon/architecture/settle-detection.md` — Citations [7] added
- **Updated:** `canon/architecture/login-automaton.md` — Citations [6] added
- **Updated:** `canon/engine/world-model.md` — Citations last bullet added
- **Updated:** `canon/strategy/trade-loops.md` — Citations chains bullet updated
- **New:** `workorders/BRIEF-OKF-ARCHIVE-PORT-PATTERNS.md` — implementer brief
- **New:** `workorders/WO-ARCHIVE-PATTERNS-INTO-CANON.md` — this file
- **Updated:** `canon/DECISIONS.md` — Accepted stamp
- **Updated:** `canon/findings.md` — row added

## Constraints

- Extract patterns and algorithms as prose + short pseudocode/signatures — do NOT copy large
  copyrighted chunks or entire modules.
- Reborn framing: rewrite any "AI drives" language into taught-app / human-sovereign terms.
- No product `.py` behavior changes.
- No `/Users/<name>/` paths in committed files.

## Accept

1. `canon/research/archive-port-patterns.md` exists with OKF frontmatter (type: Reference) and
   contains ≥10 pattern entries with: pattern ID, archive module, reborn concept link, priority P0–P2.
2. `canon/index.md` lists archive-port-patterns.md under a Research section.
3. At least 3 existing canon concepts cite archive-port-patterns.md in their Citations section.
4. Implementer brief exists at `workorders/BRIEF-OKF-ARCHIVE-PORT-PATTERNS.md` with hard pins.
5. Negative patterns (do-not-port) explicitly named.
6. No `/Users/` paths in any committed file.

## Proof

Status: DONE by Monk this session.

Patterns extracted: **14** (AP-01…AP-14):
- P0 (5): AP-01 classify stale-scrollback · AP-02 send_and_confirm · AP-03 login automaton · AP-04 skill record/replay · AP-05 haggle evidence-backed price
- P1 (6): AP-06 world-model store · AP-07 DFS chain finder · AP-08 BFS frontier · AP-09 priority engine · AP-10 WorldSnapshot/Decision model · AP-11 cockpit layout
- P2 (3): AP-12 menu crawler safety · AP-13 credits discipline · AP-14 learning dry-run

Negative/do-not-port section: 8 items explicitly listed.

## Refs

- `archive/pre-rebirth-2026-07-23/` — source
- `canon/` — target
- `BRIEF-OKF-ARCHIVE-PORT-PATTERNS.md` — implementer reading brief
