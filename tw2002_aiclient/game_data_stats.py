"""Game-data scalars on ``status`` — ship price count + hold quote label.

Canon: ``canon/engine/priority-engine.md`` Layer-1 GOALS keys ``ship_prices_count``
/ ``hold_price_label``, fed from Layer-B ``game_data`` (capture loop persists;
this module is the status merge). Off-draw refresh only — same seam as
``WorldStats`` / ``ChainScalars``.

Also merges ``ship_catalog`` — priced ``{ship_name, cost}`` rows for the
priority-engine pre-flight / catalog #4 live bridge (WO-PRIORITY-ENGINE-KERNEL).

Also merges ship-upgrade DECISIONS inputs (WO-WIRE-SHIP-SPEC-CATALOG-INTO-
UPGRADE-DECISIONS): full ``upgrade_catalog`` (ShipSpec-shaped) + optional
``upgrade_player`` / ``upgrade_cost_per_hold`` via
``ship_upgrade_decision.merge_upgrade_status_inputs``. Loop economics attach
later in ``FocusScalars`` when a priced chain is available.

**Readers (not write-only):** ``cockpit/goals.py``, ``focus_status.py``, and
``stardock_hold_plan.py`` consume these status keys via
``SHIP_PRICES_COUNT_KEY`` / ``HOLD_PRICE_LABEL_KEY``. Tip-stamp
``WO-TIP-STAMP-GAME-DATA-STATS-KEYS-LIVE`` closed the false "dead keys" audit.

Empty successful load may emit ``ship_prices_count=0`` (honest "looked, none
priced yet"). Hold label is omit-until-known (no blank key from an empty
cargo_holds tuple). Never invents numbers; never raises on the draw path.
"""

from __future__ import annotations

__all__ = [
    "GameDataStats",
    "SHIP_PRICES_COUNT_KEY",
    "HOLD_PRICE_LABEL_KEY",
    "SHIP_CATALOG_KEY",
]

SHIP_PRICES_COUNT_KEY = "ship_prices_count"
HOLD_PRICE_LABEL_KEY = "hold_price_label"
SHIP_CATALOG_KEY = "ship_catalog"


def _format_hold_label(cost_per_hold: int) -> str:
    """Human GOALS detail — matches fixture spelling (``1,200cr``)."""
    return f"{cost_per_hold:,}cr"


class GameDataStats:
    """Caches Layer-B catalog scalars for GOALS / FOCUS overlay. Never raises."""

    __slots__ = (
        "_ship_prices_count",
        "_ships_seen",
        "_hold_price_label",
        "_hold_seen",
        "_ship_catalog",
        "_ships",
        "_cost_per_hold",
    )

    def __init__(self) -> None:
        self._ship_prices_count: int | None = None
        self._ships_seen = False
        self._hold_price_label: str | None = None
        self._hold_seen = False
        self._ship_catalog: list[dict] | None = None
        self._ships: tuple = ()
        self._cost_per_hold: int | None = None

    def refresh(
        self,
        world_id: object,
        *,
        state_dir: object = None,
    ) -> None:
        """Re-read ``game_data.json`` for this world. Never raises.

        No on-disk store → leave prior observation (or unseen). An empty
        successful load may emit ``ship_prices_count=0``.
        """
        try:
            from tw2002_aiclient import game_data as _game_data

            kwargs = {}
            if state_dir is not None:
                kwargs["state_dir"] = state_dir
            path = _game_data.game_data_path(str(world_id), **kwargs)
            if not path.exists():
                return
            data = _game_data.load_world_game_data(str(world_id), **kwargs)
        except Exception:  # noqa: BLE001
            return
        priced = 0
        catalog: list[dict] = []
        try:
            for ship in data.ships:
                cost = getattr(ship, "base_cost_credits", None)
                name = getattr(ship, "ship_name", None)
                if isinstance(cost, bool) or not isinstance(cost, int):
                    continue
                if cost > 0:
                    priced += 1
                    if isinstance(name, str) and name.strip():
                        catalog.append({"ship_name": name.strip(), "cost": cost})
        except Exception:  # noqa: BLE001
            return
        self._ship_prices_count = priced
        self._ships_seen = True
        self._ship_catalog = catalog
        try:
            self._ships = tuple(data.ships)
        except Exception:  # noqa: BLE001
            self._ships = ()
        try:
            holds = data.cargo_holds
            if holds:
                cost = getattr(holds[0], "cost_per_hold", None)
                if isinstance(cost, bool) or not isinstance(cost, int) or cost < 0:
                    self._hold_seen = False
                    self._hold_price_label = None
                    self._cost_per_hold = None
                else:
                    self._hold_price_label = _format_hold_label(cost)
                    self._hold_seen = True
                    self._cost_per_hold = cost
            else:
                # Successful load, no quote yet — omit (unknown), do not emit blank.
                self._hold_seen = False
                self._hold_price_label = None
                self._cost_per_hold = None
        except Exception:  # noqa: BLE001
            pass

    def merge(self, status: object) -> dict | None:
        """Attach cached catalog keys; never mutates input; never clobbers."""
        if not isinstance(status, dict):
            return status
        if not self._ships_seen and not self._hold_seen:
            return status
        merged = dict(status)
        if self._ships_seen and merged.get(SHIP_PRICES_COUNT_KEY) is None:
            merged[SHIP_PRICES_COUNT_KEY] = self._ship_prices_count
        if self._ships_seen and merged.get(SHIP_CATALOG_KEY) is None:
            merged[SHIP_CATALOG_KEY] = list(self._ship_catalog or ())
        if self._hold_seen and merged.get(HOLD_PRICE_LABEL_KEY) is None:
            merged[HOLD_PRICE_LABEL_KEY] = self._hold_price_label
        # WO-WIRE-SHIP-SPEC-CATALOG-INTO-UPGRADE-DECISIONS: full catalog + player.
        if self._ships_seen or self._hold_seen:
            try:
                from tw2002_aiclient.ship_upgrade_decision import (
                    merge_upgrade_status_inputs,
                )

                enriched = merge_upgrade_status_inputs(
                    merged,
                    ships=self._ships if self._ships_seen else None,
                    cost_per_hold=self._cost_per_hold if self._hold_seen else None,
                )
                if isinstance(enriched, dict):
                    merged = enriched
            except Exception:  # noqa: BLE001 -- upgrade overlay must not break status
                pass
        return merged

    def wrap(self, provider):
        if provider is None:
            return None

        def _merged():
            return self.merge(provider())

        return _merged
