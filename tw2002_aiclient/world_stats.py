"""World-model scalars on ``status`` — the one field of T1 that has a producer.

**What this closes.** `cockpit/goals.py` renders its GOALS Map row from
``status["known_sectors"]``. No product code wrote it, so the row said "unknown"
on every live run while the suite stayed green on supplied values — the starved-
consumer shape `tests/test_status_vocabulary_guard.py` exists to catch.

**Why only one field.** `WO-GOALS-STATUS-VOCABULARY` scheduled five world-model
fields here. Resolving each one's producer left exactly this one standing, and
the other four are listed in that guard's allowlist with the evidence:

* ``galaxy_size`` — nothing in the package produces one, and `state_parser`
  explicitly refuses to invent one. The Map row already degrades to
  "· N sectors" without a denominator, which is why this module is useful alone.
* ``formations_count`` — needs the `catalog_provider.genesis_candidates` seam,
  which is unimplemented; with the only available provider the planner reports
  ``mode="unavailable"`` by its own first branch.
* ``stardock_found`` / ``stardock_sectors`` — read `rec["landmarks"]`, and the
  only live world-model writer (`sector_explore._ingest_settled_sector`) builds
  ``{sector, warps, port}``. Fed a screen that literally says
  ``Ports : StarDock, Class 9 (Special)``, the stored record still has
  ``landmarks == []`` and the lookup still returns ``[]``.

**Why a cache, not a read on the draw path.** `status_provider()` runs ONCE PER
DRAW (`screens.py`), not on a timer. Counting sector files costs ~5ms at 1000
sectors and ~26ms at 5000 — per draw, against a whole-process budget
(`tests/test_dead_terminal_spin.py`, 0.5s) already within ~50ms of its ceiling.
So the count is taken when the operator opens the chains popup, which already
pays for a far more expensive world-model pass on that keypress, and the draw
path only ever reads one cached integer. **Nothing here runs on a draw.**

**Staleness is bounded and honest.** The number is "sectors known as of the last
chains popup", so it can lag exploration done since. That is a real cost of the
budget above, and it is the right trade for a progress counter: a number that
lags is still true of a moment we were actually in, while no number at all is
what shipped before this. It never counts anything that was not on disk.
"""

from __future__ import annotations

__all__ = ["WorldStats"]

KNOWN_SECTORS_KEY = "known_sectors"


class WorldStats:
    """Caches world-model scalars, refreshed off the draw path.

    Same seam and same contract as `chain_status.ChainScalars` — the two compose
    by wrapping one provider in the other.
    """

    __slots__ = ("_known_sectors", "_seen")

    def __init__(self) -> None:
        self._known_sectors: int | None = None
        self._seen = False

    def refresh(self, world_id: object) -> None:
        """Re-read the world model's sector count. Never raises.

        A refresh that cannot determine the count (unreadable store, unusable
        ``world_id``, a raising world_model) leaves the previous value in place
        rather than clearing it: the cached number was genuinely observed, and
        replacing an observation with "unknown" because a *later* read failed
        would lose information without gaining honesty. Before any successful
        refresh there is no value, and this contributes nothing at all.

        `world_model` is imported here rather than at module scope because this
        module is imported by the cockpit wiring while `refresh` only runs on a
        popup keypress — the same lazy-import discipline `app.py` applies to
        `chain_search` for the same CPU-budget reason.
        """
        try:
            from tw2002_aiclient import world_model as _world_model

            count = _world_model.known_sector_count(world_id)
        except Exception:  # noqa: BLE001
            return
        if not isinstance(count, int) or isinstance(count, bool):
            return
        if count < 0:
            return
        self._known_sectors = count
        self._seen = True

    def merge(self, status: object) -> dict | None:
        """``status`` with the cached scalars added; never mutates the input.

        Returns a non-dict argument unchanged (a provider's own "no status"
        signal must survive untouched), and adds nothing before a successful
        refresh.

        **Does not clobber.** A key the caller already supplied with a
        non-``None`` value wins, so a future daemon-side producer cannot be
        silently overwritten by this cache's older number.
        """
        if not isinstance(status, dict):
            return status
        if not self._seen:
            return status
        merged = dict(status)
        if merged.get(KNOWN_SECTORS_KEY) is None:
            merged[KNOWN_SECTORS_KEY] = self._known_sectors
        return merged

    def wrap(self, provider):
        """``provider`` with these scalars merged into whatever it returns.

        A ``None`` provider wraps to ``None`` — an absent status source stays
        absent rather than becoming a callable returning a stats-only dict.
        """
        if provider is None:
            return None

        def _merged():
            return self.merge(provider())

        return _merged
