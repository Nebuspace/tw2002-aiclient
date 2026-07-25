# WO-AUDIT-MENUMAP-LOOKUP-FAILURE — Session audit F4: menumap lookup failure honesty (five-into-one collapse fix)

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **DONE** 2026-07-25 · tip **`da085a5`** (CC · cli-encode; F4 menumap honesty part of cli-encode + F3/F4 batch)
> Type: harden · Priority: P0 · Lens: L2 code-vs-canon / honesty / session-audit F4
> Refs: `tw2002_aiclient/session/` menumap path · session-audit wave

## Goal
Session-audit F4: `tw menumap` lookup-failure collapse — five distinct failure conditions (file absent, permission denied, corrupt JSON, bad top-level shape, unknown-entry) must produce distinct honest outputs, not collapse into a single empty/reassuring result. Apply the "five-into-one" lesson from the menumap fix: "no entry" ≠ "unreadable store".

## Scope
- `tw2002_aiclient/session/cli.py` / menumap command (`cmd_menumap`) — lookup failure branching
- `tests/` — five-condition probe: distinct errors for each failure mode

## Constraints
- Not `--profile` behavior; not the crawler (G2)
- `Path.glob()` silently swallows `PermissionError` — use `os.listdir()` for unreadable directory detection
- Full suite green

## Accept
1. Distinct output for each of: file absent / permission denied / corrupt JSON / bad schema / unknown entry
2. "Unreadable store" is a clear error, not "no entries"
3. Exit code: unreadable → 1; unknown-you-are-here → 0 + INCOMPLETE marker

## Proof
Five-condition probe + cli-encode batch; STATUS + SHA on origin (`da085a5` as part of batch).

## Refs
session-audit Lane D (F4) · hub Accept cli-encode `da085a5` @ 14:02:06Z (F2+cli+F6 batch) · `Path.glob()` PermissionError trap (CC process note)
