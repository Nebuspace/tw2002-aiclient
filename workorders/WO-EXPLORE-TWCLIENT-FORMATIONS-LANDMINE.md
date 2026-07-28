# WO-EXPLORE-TWCLIENT-FORMATIONS-LANDMINE — Disarm unresolvable imports (class)

**Status:** OPEN · EXECUTE · HIGH · Claude Code · impl-claudecode-aiclient  
**Posted:** 2026-07-28T03:45Z · EXEC seeded 03:48Z · **scope widened 03:49Z** (CC sequencing)  
**Refs:** CC STATUS 2026-07-28T03:44:20Z · ACK 03:46:27Z · ADR-001 deleted `twclient` · seed site `explore.py:493`

## Goal
Disarm **every unresolvable import** in `tw2002_aiclient/` that can fire at runtime — not only
`explore.py:493`. Seed finding was `from twclient.formations import catalog_world` inside
`plan_find_formations` (function-level; suite-green until first caller). Grep shows ~15
`twclient` mentions — must split live Import/ImportFrom vs prose before claiming all-clear.

## Accept
1. **Enumerate first** (AST Import/ImportFrom including function-level + TYPE_CHECKING): every
   target that fails `importlib.util.find_spec`, crossed with reachability:
   - unresolvable **inside reachable code** → **must fix in this WO** (live bug)
   - unresolvable **only inside already-dead code** → bank cleanup, do not block all-clear
2. For each live bug: remove/replace with honest refuse or in-tree path — **no** resurrect of
   `twclient` / other deleted packages.
3. Pin(s): each fixed call path does not raise `ModuleNotFoundError` for the dead package;
   named behaviour tested. Note when enclosing fn has no real test caller.
4. Grep/AST: zero remaining **live** unresolvable imports in reachable product code (prose OK).
5. Suite + STATUS; live-prove n/a unless a live path exists.
6. If enumeration finds **exactly one** live site (`explore.py:493`), WO is unchanged in
   substance — still report the enum table so all-clear is evidenced, not assumed.

## Constraints
Do not wire N-port (#139) until this all-clear. Do not invent formations product. Public-repo safe.
