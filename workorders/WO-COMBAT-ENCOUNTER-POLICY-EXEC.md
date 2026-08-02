# WO-COMBAT-ENCOUNTER-POLICY-EXEC — NPC auto-fight at force_share ≥ 0.90

**Status:** DONE · origin `5ffb264` (#206) · tip-honesty stamp 2026-08-02 (exec ship shared with policy WO; banner was stale OPEN/EXECUTE)
**Posted:** 2026-07-28T22:36Z · Max GO — formula + canon auto-fight amend  
**Depends:** canon patch on this branch (`toll-and-defense.md` + DECISIONS RESOLVED)  
**Refs:** banked `WO-COMBAT-ENCOUNTER-POLICY` · CC CANON-CONFLICT 22:34Z

## Max ruling (this EXEC)

1. **force_share** = `own / (own + enemy)` (name it that — not `win_est`).
2. Autonomous **NPC** fight when `force_share ≥ 0.90` (⇔ own:enemy ≥ 9:1) **and** enemy count within `winnable_enemy_band` (config; default ≤3).
3. Else Retreat; unparseable counts ⇒ STOP/Retreat per canon safe exit; **never Pay**; **PvP ⇒ hard STOP**.
4. Scope includes follow-up **`How many fighters…`** prompt (no strand mid-combat) — **one flow with Option?**, not two independent classifiers.
5. Both counts must be **present** before arithmetic (parsed zero ≠ missing).
6. **Qty-prompt fail-closed (CC 22:37 finding):** unparseable counts at quantity ⇒ STOP/Retreat — **never** archive `return max_avail`. Pin against that fallback. Idle/`[0]` must not re-fire `A` forever.

## Accept

1. Classify `Option? (A,D,I,R,S,?)` · parse vs-line · three-branch decide with pins + mutation that STOP cannot be masked.
2. Quantity prompt in same encounter flow; unparsed ⇒ STOP (never `max_avail`); falsification pin on that fallback.
3. Config parameters cited (canon schema names) — unset/fail-closed never fights.
4. Canon on branch matches Max amend (auto-Attack restored under the gates above; divergence note updated).
5. Suite green · live DEFERRED → Cursor.

## Constraints

Safety-list adjacent. No canon invent beyond Max amend on this branch. Public-safe.
