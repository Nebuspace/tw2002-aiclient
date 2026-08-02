"""World-model scalars on ``status`` — Map count + StarDock + ``has_port`` (T1).

**What this closes.** `cockpit/goals.py` renders its GOALS Map row from
``status["known_sectors"]`` and its StarDock row from ``stardock_sectors`` /
``stardock_found``. Both were starved consumers: suites stayed green on
supplied fixtures while live runs painted ``?``. This cache is the client-side
producer for the fields whose world-model readers already exist.

``has_port`` (WO-COACH-HAS-PORT) feeds idle DECISIONS coaching: when the HUD
sector is a real int and the world-model record for that sector carries a
port, merge ``has_port=True``. Unknown / missing sector / no port observation
**omits** the key (never invents confirmed-negative ``False``).

``dead_end_count`` (WO-COACH-DEAD-END-COUNT) counts world-model sectors whose
``warps`` list has length exactly 1 (colonization dead-ends — **not**
menu-map signature dead-ends). Pre-scan **omits**; a completed scan may
report ``0``.

``formations_count`` / ``genesis_count`` / ``formations_panel``
(WO-FORMATIONS-CATALOG-PORT): same dead-end scan feeds the in-tree catalog.
Under the dead-end-only detector, ``formations_count`` (panel item count)
equals ``genesis_count`` (genesis-kind candidates). ``formations_panel`` is
``{"items": [{"name", "blurb"}, ...]}`` for the FORMATIONS gutter.

**What stays allowlisted.** Other GOALS world-model keys still have no honest
producer here:

* ``galaxy_size`` — nothing in the package produces one, and `state_parser`
  explicitly refuses to invent one. The Map row already degrades to
  "· N sectors" without a denominator.

StarDock is **not** starved at the landmarks layer anymore: explore / ingest
writers record ``landmarks[]``, and ``explore.find_landmark_sectors`` +
``world_model.STARDOCK_LANDMARK`` are the single spelling table this module
reuses (no second landmark vocabulary).

**Empty scan ≠ confirmed-negative.** A successful refresh that finds no
StarDock sectors **omits** both keys so GOALS stays ``?``. Emitting
``stardock_found=False`` would mean *confirmed not found* and wrongly gate
Ship/Hold rows — never do that from an empty landmark scan.

**Why a cache, not a read on the draw path.** `status_provider()` runs ONCE PER
DRAW (`screens.py`), not on a timer. Counting sector files costs ~5ms at 1000
sectors and ~26ms at 5000 — per draw, against a whole-process budget
(`tests/test_dead_terminal_spin.py`, 0.5s) already within ~50ms of its ceiling.
Landmark scans walk sector records. So both scalars are taken when the operator
opens the chains popup (which already pays for a far more expensive world-model
pass on that keypress) or when an explore run reaches a terminal outcome on the
idle poll (already paid for `explore_status`), and the draw path only ever reads
the cached values. **Nothing here runs on a draw.**

**Staleness is bounded and honest.** The numbers are "as of the last chains
popup or the last explore terminal poll", so they can lag exploration done
since without those events. That is a real cost of the budget above, and it is
the right trade for a progress counter / landmark disclosure: a value that lags
is still true of a moment we were actually in, while no value at all is what
shipped before this. It never reports anything that was not on disk.
"""

from __future__ import annotations

__all__ = ["WorldStats"]

KNOWN_SECTORS_KEY = "known_sectors"
STARDOCK_SECTORS_KEY = "stardock_sectors"
STARDOCK_FOUND_KEY = "stardock_found"
HAS_PORT_KEY = "has_port"
DEAD_END_COUNT_KEY = "dead_end_count"
FORMATIONS_COUNT_KEY = "formations_count"
GENESIS_COUNT_KEY = "genesis_count"
FORMATIONS_PANEL_KEY = "formations_panel"


def _sector_from_status(status: object) -> int | None:
    """HUD sector id when it is a real ``int``; else ``None``. Never raises."""
    if not isinstance(status, dict):
        return None
    hud = status.get("hud")
    if not isinstance(hud, dict):
        return None
    cell = hud.get("sector")
    if not isinstance(cell, dict):
        return None
    value = cell.get("value")
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


class WorldStats:
    """Caches world-model scalars, refreshed off the draw path.

    Same seam and same contract as `chain_status.ChainScalars` — the two compose
    by wrapping one provider in the other.
    """

    __slots__ = (
        "_known_sectors",
        "_seen",
        "_stardock_sectors",
        "_stardock_seen",
        "_has_port_seen",
        "_dead_end_count",
        "_dead_end_seen",
        "_formations_count",
        "_genesis_count",
        "_formations_panel",
        "_formations_seen",
    )

    def __init__(self) -> None:
        self._known_sectors: int | None = None
        self._seen = False
        self._stardock_sectors: list[int] = []
        self._stardock_seen = False
        self._has_port_seen = False
        self._dead_end_count: int | None = None
        self._dead_end_seen = False
        self._formations_count: int | None = None
        self._genesis_count: int | None = None
        self._formations_panel: dict | None = None
        self._formations_seen = False

    def refresh(
        self,
        world_id: object,
        *,
        status: object = None,
        state_dir: object = None,
    ) -> None:
        """Re-read world-model scalars. Never raises.

        Known-sector count and StarDock landmarks refresh independently: a
        failure on one leaves that cache's previous observation in place and
        does not block the other. Before any successful refresh of a scalar
        there is no value, and that scalar contributes nothing at merge.

        ``has_port`` refreshes only when ``status`` is supplied (needs the HUD
        sector). A completed lookup that does not observe a port clears any
        prior True so a move to an unknown sector cannot leave a stale card.

        ``dead_end_count`` / formations scalars scan on every refresh (same
        cadence as known sectors). A completed scan may report ``0``; failure
        leaves the prior observation in place.

        `world_model` / `explore` are imported here rather than at module scope
        because this module is imported by the cockpit wiring while `refresh`
        only runs on a popup keypress — the same lazy-import discipline
        `app.py` applies to `chain_search` for the same CPU-budget reason.
        """
        self._refresh_known_sectors(world_id, state_dir=state_dir)
        self._refresh_stardock(world_id, state_dir=state_dir)
        self._refresh_dead_ends(world_id, state_dir=state_dir)
        if status is not None:
            self._refresh_has_port(world_id, status, state_dir=state_dir)

    def _refresh_known_sectors(
        self, world_id: object, *, state_dir: object = None
    ) -> None:
        try:
            from tw2002_aiclient import world_model as _world_model

            kwargs = {}
            if state_dir is not None:
                kwargs["state_dir"] = state_dir
            count = _world_model.known_sector_count(world_id, **kwargs)
        except Exception:  # noqa: BLE001
            return
        if not isinstance(count, int) or isinstance(count, bool):
            return
        if count < 0:
            return
        self._known_sectors = count
        self._seen = True

    def _refresh_stardock(
        self, world_id: object, *, state_dir: object = None
    ) -> None:
        try:
            from tw2002_aiclient import explore as _explore
            from tw2002_aiclient import world_model as _world_model

            kwargs = {}
            if state_dir is not None:
                kwargs["state_dir"] = state_dir
            raw = _explore.find_landmark_sectors(
                world_id, _world_model.STARDOCK_LANDMARK, **kwargs
            )
        except Exception:  # noqa: BLE001
            return
        if not isinstance(raw, list):
            return
        sectors: list[int] = []
        for item in raw:
            if isinstance(item, bool) or not isinstance(item, int):
                return
            sectors.append(item)
        self._stardock_sectors = sectors
        self._stardock_seen = True

    def _refresh_dead_ends(
        self, world_id: object, *, state_dir: object = None
    ) -> None:
        """Count one-warp sectors + feed formations scalars. Never raises.

        Completed scan (including zero) sets ``_dead_end_seen`` and
        ``_formations_seen``. A raising or hostile ``all_sectors`` leaves the
        prior observation untouched — never invents a positive count from junk.

        Under WO-FORMATIONS-CATALOG-PORT's dead-end-only catalog,
        ``formations_count`` == ``genesis_count`` == dead-end count.
        """
        try:
            from tw2002_aiclient import world_model as _world_model

            kwargs = {}
            if state_dir is not None:
                kwargs["state_dir"] = state_dir
            sectors = _world_model.all_sectors(world_id, **kwargs)
        except Exception:  # noqa: BLE001
            return
        if not isinstance(sectors, list):
            return
        dead_end_ids: list[int] = []
        for record in sectors:
            if not isinstance(record, dict):
                return
            warps = record.get("warps")
            if not isinstance(warps, list):
                continue
            if len(warps) != 1:
                continue
            sid = record.get("sector_id")
            if isinstance(sid, bool) or not isinstance(sid, int):
                continue
            dead_end_ids.append(sid)
        dead_end_ids.sort()
        count = len(dead_end_ids)
        self._dead_end_count = count
        self._dead_end_seen = True
        # Same observation feeds the formations panel / GOALS count / coach.
        items = [
            {
                "name": f"Dead-end #{sid}",
                "blurb": "one warp — defensible siting candidate",
            }
            for sid in dead_end_ids
        ]
        self._formations_count = count
        self._genesis_count = count
        self._formations_panel = {"items": items}
        self._formations_seen = True

    def _refresh_has_port(
        self,
        world_id: object,
        status: object,
        *,
        state_dir: object = None,
    ) -> None:
        """Observe port presence for the HUD sector. Never raises.

        Emit path is omit-until-known: only a completed lookup that finds a
        non-``None`` ``port`` on the sector record sets ``_has_port_seen``.
        Missing sector, unknown sector, empty port, or hostile HUD clears the
        flag so merge omits the key.
        """
        sector = _sector_from_status(status)
        if sector is None:
            self._has_port_seen = False
            return
        try:
            from tw2002_aiclient import world_model as _world_model

            kwargs = {}
            if state_dir is not None:
                kwargs["state_dir"] = state_dir
            record = _world_model.get_sector(world_id, sector, **kwargs)
        except Exception:  # noqa: BLE001
            # Failed lookup for a known sector id: omit rather than keep a
            # possibly-stale True from a previous sector (coaching fail-closed).
            self._has_port_seen = False
            return
        if not isinstance(record, dict):
            self._has_port_seen = False
            return
        port = record.get("port")
        self._has_port_seen = port is not None

    def merge(self, status: object) -> dict | None:
        """``status`` with the cached scalars added; never mutates the input.

        Returns a non-dict argument unchanged (a provider's own "no status"
        signal must survive untouched), and adds nothing for a scalar before
        that scalar has successfully refreshed.

        **Does not clobber.** A key the caller already supplied with a
        non-``None`` value wins, so a future daemon-side producer cannot be
        silently overwritten by this cache's older value.

        **Empty StarDock scan omits keys.** A successful refresh that found no
        landmarks does not emit ``stardock_found=False``.

        **``has_port`` is True-or-omit.** Never merges ``False``.

        **``dead_end_count`` / formations:** omitted until a completed scan;
        then non-negative ints (including ``0``) and a panel payload.
        """
        if not isinstance(status, dict):
            return status
        if (
            not self._seen
            and not self._stardock_seen
            and not self._has_port_seen
            and not self._dead_end_seen
            and not self._formations_seen
        ):
            return status
        merged = dict(status)
        if self._seen and merged.get(KNOWN_SECTORS_KEY) is None:
            merged[KNOWN_SECTORS_KEY] = self._known_sectors
        if self._stardock_seen and self._stardock_sectors:
            if merged.get(STARDOCK_SECTORS_KEY) is None:
                merged[STARDOCK_SECTORS_KEY] = list(self._stardock_sectors)
            if merged.get(STARDOCK_FOUND_KEY) is None:
                merged[STARDOCK_FOUND_KEY] = True
        if self._has_port_seen and merged.get(HAS_PORT_KEY) is None:
            merged[HAS_PORT_KEY] = True
        if self._dead_end_seen and merged.get(DEAD_END_COUNT_KEY) is None:
            merged[DEAD_END_COUNT_KEY] = self._dead_end_count
        if self._formations_seen:
            if merged.get(FORMATIONS_COUNT_KEY) is None:
                merged[FORMATIONS_COUNT_KEY] = self._formations_count
            if merged.get(GENESIS_COUNT_KEY) is None:
                merged[GENESIS_COUNT_KEY] = self._genesis_count
            if merged.get(FORMATIONS_PANEL_KEY) is None and self._formations_panel is not None:
                merged[FORMATIONS_PANEL_KEY] = {
                    "items": list(self._formations_panel.get("items", [])),
                }
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
