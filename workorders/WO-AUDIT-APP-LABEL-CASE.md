# WO-AUDIT-APP-LABEL-CASE — Canon “App” vs shipped `APP`

> Status: **DRAFT** 2026-07-25 · AUDIT-OKF-6LENS · Priority: P2 · Lens: L2 · MICRO-SCOUT pin tip `78f4bb5`  
> Type: polish · Refs: `control_seat.APP_LABEL` · `mode-line-and-teach-controls.md`  
> **PARKED:** Max/hub ruling — do not invent overnight; scout pins only

## Scout pin (origin `78f4bb5`)
| Surface | Path:line | Text |
|---|---|---|
| Product chip | `tw2002_aiclient/cockpit/control_seat.py:178` | `APP_LABEL = "APP"` |
| Accessor | `control_seat.py:233-241` | `app_label()` always returns `APP_LABEL` |
| Comment | `control_seat.py:163` | notes `"APP"` is a new single chip (not reuse of as-built literal) |
| Canon prose | `canon/surfaces/mode-line-and-teach-controls.md:23,29` | short label **App** (Title case) |
| Canon tone | `canon/surfaces/visual-language.md:95` | **App** — green (`ok`) |

## Goal
Resolve display-string tension: canon short label **App** vs tip chip text `APP` — either update canon to match shipped uppercase chip, or change label + tests to Title case.

## Scope
- A: Hub/Max one-line ruling (canon vs code)
- B: Single-file label + matrix tests OR canon prose — not both without ruling
- C: visual-language / mode-line tip notes

## Constraints
No seat-key changes. Vocabulary gate must stay clean. Prefer docs-win if Max silent → update canon to `APP` as shipped (smallest product risk). Do not edit `control_seat.py` until Max/hub GO.

## Accept
One spelling in canon + product tip; tests/matrix updated if code changes.

## Proof
`rg APP_LABEL` + chip matrix · docs or product commit. Push waits Accept.

## Refs
`control_seat.py:178` · OKF-060 tip-stamp · backlog A-L2-APP-LABEL
