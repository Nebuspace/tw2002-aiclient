# WO-COMBAT-ENCOUNTER-POLICY — programmatic fight/retreat on encounter prompt

**Status:** DONE · origin `5ffb264` (#206) · tip-honesty stamp 2026-08-02 (product on main; banner was stale OPEN/EXECUTE)
**Posted:** 2026-07-28T02:52Z · hub bank from #128 live mine/fighter halt  
**Refs:** Max wording quoted in CC STATUS 2026-07-28T02:51:51Z · AP-12 emit_key_if_safe

## Max policy (verbatim — do not paraphrase into canon without Max)

- Mine case: retreat unless we have fighters, in which case fight.
- Programmatic fights OK when statistical chance of winning is **north of 90%**.
- Standing rule: unknown screen ⇒ analyse deeply + bank a WO for programmatic response (stop alone is incomplete).

## Observed screen (tonight)
`Option? (A,D,I,R,S,?):?` after mine + corp fighters. Game prints `Your fighters: 89 vs. theirs: 1` — ratio is **observed, not estimated**. 89:1 ≫ 90% ⇒ FIGHT under Max rule. Halt lost a Class 5 SBS port this path wanted.

## Accept
1. Classify encounter prompt `Option? (A,D,I,R,S,?)`.
2. Parse own vs enemy fighter counts from screen; **fight only when observed ratio clears Max-ratified threshold**; else retreat; **STOP (never guess)** if either count unparseable.
3. Threshold = **cited config parameter**, not a hardcoded constant.
4. Menu discovery via deny-by-default / AP-12 (`?` read-only) — do not assume letter meanings.
5. Pins for fight / retreat / unparseable-STOP. Suite + STATUS.
6. Canon: Pending DECISION / doctrine stub only with Max GO on prose — seat may implement against this WO + quoted policy until canon lands.

## Constraints
Safety-list adjacent (combat automation). Fail-closed on unreadable counts. Public-repo safe. Not #128 scope.
