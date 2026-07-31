# WO-FIGHTER-TOLL-POLICY-WIRE — product consumer for `fighter_toll_policy`

**Status:** DONE · origin `ad232da` (#209) · tip-honesty stamp 2026-07-31 (product on main; banner was stale OPEN)
**Seat:** Claude Code (`impl-claudecode-aiclient`) · Live DEFERRED → Cursor
**Refs:** #206 EXEC · #207 classify ruling (a) · CC STATUS 00:33Z findings · Max combat GO (force_share≥0.90)

## Why

`fighter_toll_policy` + `fighter_encounter` class are on main with **zero product importers** (tests + comments only). Classify hole is closed; policy still cannot fire. This WO is the guarded owner wire.

## Goal

When the live screen classifies `fighter_encounter` (and, in the same flow, the qty `money_prompt` owned by this policy), the **armed** explore/autoloop/player send path calls `decide_encounter` / qty helpers and sends only the decided key — never Pay, never blind Attack.

## Accept

1. **Product caller** of `fighter_toll_policy.decide_encounter` (and qty path) outside `tests/` — pin via AST/import that a real loop/explore boundary invokes it on `fighter_encounter`.
2. **`key=None` / `reason=not_encounter` / undetected:** do **not** act; escalate/halt per existing refuse ladder. Explicit pin: `halt=False` on that return is **not** permission to send. (CC finding — write into pins.)
3. Armed-only: disarmed / human-at-keyboard / fence still refuse before policy.
4. Qty frame stays classified `money_prompt`; policy owns the bounded step without reclassifying.
5. **Single-source Option? regex (banked):** either share one compiled pattern between `classify` gate anchor and `fighter_toll_policy._OPTION_PROMPT_RE`, or document intentional subset with a pin that policy-detect ⇒ classify-names (already on #207) plus a non-drift Accept that future edits touch one module. Prefer one source if cheap.
6. Mutations: unwire product caller → red; treat `key=None` as send → red; Pay letter never sent.
7. Suite green · live DEFERRED → Cursor (diversity; sacrificial turns only under Max combat GO — hub GO safe half first if needed).

## Constraints

Safety-list adjacent. No widen to bare `Option?`. No invent beyond Max combat GO. Public-safe. Do not flip explore dock default.

## Out of scope

Dock dialect residual; unused-code batch WOs.
