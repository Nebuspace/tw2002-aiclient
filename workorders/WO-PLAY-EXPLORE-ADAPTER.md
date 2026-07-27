# WO-PLAY-EXPLORE-ADAPTER

**Status:** OPEN · **depends on** `WO-PLAY-WORLD-IDENTITY` on `main` (or same PR if sequential commits)  
**Posted:** 2026-07-27T03:10:33Z · One-client Play ladder **L2**  
**Seat:** impl-aiclient-cursor  
**Plan:** `.samantha/plans/one-client-play-ladder-20260727.md`

## Goal

Give Play a typed adapter for explore — mirror `ensure_session` — so the TUI never shells `tw explore`.

## Contract (pin for L3 parallel)

```python
@dataclass(frozen=True)
class ExploreResult:
    ok: bool
    reason: str | None = None   # machine-readable when ok=False
    detail: str | None = None
    raw: dict | None = None     # wire dict; L4 reads distinct_sectors/outcome from here or typed fields

def explore_start(
    world_id: str,
    *,
    min_sectors: int = 5,
    turn_budget: int = 50,
    run_dir: Path | None = None,
) -> ExploreResult: ...

def explore_start_for_profile(
    profile,  # object with host / game_letter / handle OR name resolvable to those
    *,
    min_sectors: int = 5,
    turn_budget: int = 50,
    run_dir: Path | None = None,
) -> ExploreResult:
    """Derive world_id via world_identity; then explore_start."""

def explore_status(*, run_dir: Path | None = None) -> ExploreResult: ...
def explore_stop(*, run_dir: Path | None = None) -> ExploreResult: ...
```

Transport: `session.cli.send_request("explore_start"|…)` — same as CLI. Never raise for expected wire failures; return `ok=False`.

## Scope (owned)

- `tw2002_aiclient/adapters.py`
- `tests/test_adapters_explore.py` (new) — mock `send_request`; pin payload mapping + `explore_start_for_profile` uses `world_identity`

## Out of scope

- `app.py` / `screens.py` / cockpit chrome (L3/L4)
- `session/protocol.py` / `sector_explore.py` behavior changes
- New CLI verbs

## Accept

1. `explore_start("slug", min_sectors=5)` → `send_request("explore_start", {"world_id":"slug","min_sectors":5})` (omit defaults only if CLI does — match CLI payload discipline from `cmd_explore_start`)
2. `explore_status` / `explore_stop` send matching verbs
3. `explore_start_for_profile` derives slug via `world_identity.world_id_from_profile` (or equivalent) — unit-tested with a duck profile
4. Failures → `ExploreResult(ok=False, …)` never bare exceptions for transport/protocol errors
5. `pytest tests/test_adapters_explore.py tests/test_world_identity.py -q -n0`

## Proof

Unit tests above. Optional hub secondary: after ensure on micro, call adapter from a one-shot Python snippet — **not** required for Accept if units pin the wire.

## Refs

- `tw2002_aiclient/adapters.py` (`ensure_session`)
- `tw2002_aiclient/session/cli.py` (`cmd_explore_*`)
- `workorders/WO-EXPLORE-CLI-INVOKE.md` (DONE — protocol already live)
- `workorders/WO-PLAY-WORLD-IDENTITY.md`
