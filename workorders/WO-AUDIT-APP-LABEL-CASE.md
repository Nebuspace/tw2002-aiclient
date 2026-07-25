# WO-AUDIT-APP-LABEL-CASE — Canon “App” vs shipped `APP`

> Status: **EXECUTED / Ruled** 2026-07-25 · Max Batch 2/3 · Priority: P2 · Lens: L2  
> Type: polish · Refs: `control_seat.APP_LABEL` · `mode-line-and-teach-controls.md`  
> **Ruling:** chip spelling = **`APP`** (docs-win; match shipped `APP_LABEL="APP"`). No product rename.

## Scout pin (origin `78f4bb5`)
| Surface | Path:line | Text |
|---|---|---|
| Product chip | `tw2002_aiclient/cockpit/control_seat.py:178` | `APP_LABEL = "APP"` |
| Accessor | `control_seat.py:233-241` | `app_label()` always returns `APP_LABEL` |
| Canon | mode-line / visual-language / findings | stamped chip text **`APP`**; actor prose may still say App |

## Accept
Docs stamp cites Max Batch 2/3; product left alone (`APP` already correct).

## Proof
findings + mode-line + visual-language + backlog. Push waits Accept.
