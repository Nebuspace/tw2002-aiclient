# WO-AUDIT-ATTACH-SEND-EMPTY — Session audit F2: attach send_key empty/None guard

> Reconstructed from coord HANDOFF bodies (2026-07-25 backfill).
> Status: **DONE** 2026-07-25 · tip **`eb709df`** (CC · F2-daemon; part of F2+cli+F6 batch `1198dce` on origin)
> Type: harden · Priority: P0 · Lens: L2 code-vs-canon / session-audit F2
> Refs: `tw2002_aiclient/session/` attach path · session-audit wave

## Goal
Session-audit F2: guard `send_key` / daemon attach handler against empty or `None` key values — reject or drop rather than forwarding an empty byte string on the wire.

## Scope
- `tw2002_aiclient/session/daemon.py` — attach/`send_key` handler (F2-daemon path)
- `tests/` — empty/None send_key probe red→green

## Constraints
- Disjoint from Lane C (SURROGATE-ASCII on `cli.py`) — daemon path only
- Serialized with SURROGATE-ASCII for `daemon.py` access; resolved by daemon-lane ownership
- Full suite green

## Accept
1. Empty or `None` `send_key` value rejected / dropped (not forwarded as empty byte string)
2. Typed error or silent-drop — honest; no crash
3. Full suite green

## Proof
F2-daemon probe red→green; STATUS + SHA (`eb709df` on origin as part of `1198dce` batch).

## Refs
session-audit Lane B · hub Accept F2-daemon `eb709df` @ 14:02:06Z · batch `1198dce` on origin
