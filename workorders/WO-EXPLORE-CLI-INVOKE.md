# WO-EXPLORE-CLI-INVOKE

**Status:** DONE — PR #59 · SHA 5399ae8  
**Posted:** 2026-07-27 · Max try-path — M4 must be operator-reachable  
**Seat:** impl-aiclient-cursor (volume · well-spec'd CLI)  
**Depends:** `WO-EXPLORE-SECTOR-FRONTIER` DONE (`6ea004b`) — `ExploreRunner` + protocol already on `main`

## Goal

Expose existing daemon explore verbs on the CLI so Max (and hub live-prove) can run:

```text
tw ensure <profile> … → main_command
tw explore start --world-id <slug> [--min-sectors N] [--turn-budget N]
tw explore status
tw explore stop
```

Engine is done; this WO is the **missing invoke surface** only.

## Scope (owned)

- `tw2002_aiclient/session/cli.py` — nested `explore` → `start|stop|status`; copy `cmd_do` / `send_request` / `print_response` pattern (`cli.py` ~443–501, parser ~1269+)
- `tests/test_cli_explore_wiring.py` (new) — argparse + mocked `send_request` payload mapping

## Out of scope

- `protocol.py` / `sector_explore.py` / `daemon.py` / planner / screen classes — **do not invent**
- Cockpit / Play UI wire (follow-on WO)
- Autopilot / `game_select` halt behavior
- Canon prose push (`sw2102-docs`) · README only if a one-line verb list already exists in-repo and needs the new verb named

## Protocol contract (forward only)

| Verb | Args |
|---|---|
| `explore_start` | **required** `world_id` (str); optional `min_sectors` (default 5), `turn_budget` (default 50) |
| `explore_stop` | none |
| `explore_status` | none |

Reject unknown start args the same way the protocol does (`ARGS_EXPLORE_START`).

## Accept

1. `tw explore start --world-id X` sends `explore_start` with `{"world_id":"X"}` (+ optional flags when set); exit non-zero when `ok:false`
2. `tw explore stop` / `status` send the matching verbs with empty payloads
3. Wiring test covers all three verbs (mock `send_request`) — no live TWGS required for unit Accept
4. Nested help: `tw explore --help` / `tw explore start --help` exit 0 and name the flags
5. Zero product changes outside `session/cli.py` + the new test file

## Proof

```text
pytest tests/test_cli_explore_wiring.py -q -n0
# optional smoke after ensure on sacrificial host (hub may live-prove):
#   tw explore start --world-id <slug> --min-sectors 5
#   tw explore status   # until outcome completed | halted
```

## Refs

- `tw2002_aiclient/session/protocol.py` (`_dispatch_explore_*`)
- `tw2002_aiclient/session/sector_explore.py` (`ARGS_EXPLORE_START`, `DEFAULT_MIN_DISTINCT_SECTORS`)
- `workorders/WO-EXPLORE-SECTOR-FRONTIER.md` (DONE)
- Sprint honesty: M4 engine ≠ Max-tryable without this invoke
