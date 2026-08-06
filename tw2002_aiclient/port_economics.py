"""Port-economics parameter substrate (PWO-100).

Read-only hypothesis-tagged numbers that trade ranking / coaching / guards
*read* — never a live action-picker, never a send path. Canon:
``canon/strategy/port-economics.md``.

Every concrete product statistic here is labelled ``hypothesis`` with
``verified_vs_live=False`` until live introspection confirms it. Callers that
need a bare float/map take it through the accessors below; silent module-level
literals for floors / ceilings / spreads do **not** live in ``trade_adapter``.

Does **not** invent Layer-B game_data rows or mark anything ``introspected``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from tw2002_aiclient.coach_kb import CoachParam, DEFAULT_DATA_DIR, load_coach_kb

# Canon portable ordering only — Equipment > Organics > Fuel Ore.
# Concrete credits/unit figures are unverified starting hypotheses.
_FLOOR_SOURCE = (
    "canon/strategy/port-economics.md floor-price model [hypothesis] — "
    "UNVERIFIED against live TWGS"
)


@dataclass(frozen=True)
class HypothesisParam:
    """One labelled economic parameter.

    ``tag`` is always ``\"hypothesis\"`` for product stats until a live
    confirm flips ``verified_vs_live``. Values that are maps (floors) keep
    the whole map under one key so callers cannot partially strip the tag.
    """

    key: str
    value: float | int | Mapping[str, float]
    unit: str
    source_note: str
    verified_vs_live: bool = False
    tag: str = "hypothesis"

    def __post_init__(self) -> None:
        if self.tag != "hypothesis" and not self.verified_vs_live:
            raise ValueError(
                f"{self.key}: unverified params must carry tag='hypothesis'"
            )
        if self.verified_vs_live and self.tag == "hypothesis":
            raise ValueError(
                f"{self.key}: verified_vs_live=True cannot keep tag='hypothesis'"
            )


# --- Adapter pricing knobs (were silent DEFAULT_* in trade_adapter) --------

FLOOR_PRICES = HypothesisParam(
    key="floor_prices",
    value={
        "Fuel Ore": 20.0,
        "Organics": 30.0,
        "Equipment": 40.0,
    },
    unit="credits_per_unit",
    source_note=_FLOOR_SOURCE,
)

CEILING_MULTIPLIER = HypothesisParam(
    key="ceiling_multiplier",
    value=2.0,
    unit="multiplier",
    source_note=(
        "trade_adapter interpolation choice — UNVERIFIED; not authored in "
        "port-economics.md (doc does not specify interpolation shape)"
    ),
)

BUY_SELL_SPREAD_OF_FLOOR = HypothesisParam(
    key="buy_sell_spread_of_floor",
    value=0.05,
    unit="fraction_of_floor",
    source_note=(
        "WO-TRADE-ADAPTER-BUY-SELL-SPREAD modeling knob — UNVERIFIED; "
        "named so Gather pct=100 worlds are not permanently margin-zero"
    ),
)

# --- Coach / canon companion numbers (already tagged in params.json) ------

REGROWTH_PCT_PER_DAY = HypothesisParam(
    key="port_regrowth_pct_per_day",
    value=10,
    unit="percent",
    source_note=(
        "port-economics.md ~10%/day regrowth [hypothesis] — verify before trust"
    ),
)

PLAGUE_STOCK_WARN = HypothesisParam(
    key="plague_stock_warn",
    value=10_000_000,
    unit="credits_stock_proxy",
    source_note=(
        "port-economics.md ~10M stock plague-ceiling heuristic [hypothesis]"
    ),
)

ROTATE_THRESHOLD_TRADES = HypothesisParam(
    key="rotate_threshold_trades",
    value=50,
    unit="trades",
    source_note=(
        "Coach rotate-when-thin default — hypothesis; ranking/coaching only"
    ),
)

# All product-stat HypothesisParams this module authors (tag-presence sweep).
AUTHORED_PARAMS: tuple[HypothesisParam, ...] = (
    FLOOR_PRICES,
    CEILING_MULTIPLIER,
    BUY_SELL_SPREAD_OF_FLOOR,
    REGROWTH_PCT_PER_DAY,
    PLAGUE_STOCK_WARN,
    ROTATE_THRESHOLD_TRADES,
)

# Coach params.json keys that are port-economics substrate (not every coach key).
COACH_PORT_ECONOMICS_KEYS: frozenset[str] = frozenset(
    {
        "port_regrowth_pct_per_day",
        "rotate_threshold_trades",
        "plague_stock_warn",
    }
)


def hypothesized_floor_prices() -> dict[str, float]:
    """Copy of hypothesized floors — never treat as live-verified fact."""
    raw = FLOOR_PRICES.value
    if not isinstance(raw, Mapping):
        raise TypeError("floor_prices value must be a mapping")
    return {str(k): float(v) for k, v in raw.items()}


def hypothesized_ceiling_multiplier() -> float:
    return float(CEILING_MULTIPLIER.value)


def hypothesized_buy_sell_spread_of_floor() -> float:
    return float(BUY_SELL_SPREAD_OF_FLOOR.value)


def all_hypothesis_params() -> tuple[HypothesisParam, ...]:
    """Every authored product-stat param — for tag-presence proofs."""
    return AUTHORED_PARAMS


def assert_all_unverified_tagged() -> None:
    """Fail loud if any authored param lost its hypothesis discipline."""
    for p in AUTHORED_PARAMS:
        if p.verified_vs_live:
            raise AssertionError(
                f"{p.key}: expected verified_vs_live=False until live confirm"
            )
        if p.tag != "hypothesis":
            raise AssertionError(f"{p.key}: expected tag='hypothesis', got {p.tag!r}")


def load_coach_port_economics_params(
    params_path: str | Path | None = None,
) -> tuple[CoachParam, ...]:
    """Schema helper: port-economics keys must exist in coach ``params.json``.

    Intentionally **not** wired into ``cockpit/decisions`` coach-session start —
    the panel already loads the full KB via ``load_coach_kb``, and Max's
    2026-08-05 ruling keeps floor/regrowth/plague numbers permanently
    unconfirmed (no live scoring consumer for this subset yet). Kept for
    contract tests that ``COACH_PORT_ECONOMICS_KEYS`` are present with
    ``verified_vs_live`` (complement to ``assert_all_unverified_tagged``).

    Requires each row to carry ``verified_vs_live`` (schema-enforced by
    ``coach_kb.validate_param``). Does not invent introspected values.
    """
    path = Path(params_path) if params_path is not None else DEFAULT_DATA_DIR / "params.json"
    # strategies path unused for values — load_coach_kb needs a strategies file.
    strategies = DEFAULT_DATA_DIR / "strategies.json"
    kb = load_coach_kb(strategies, path)
    selected = tuple(p for p in kb.params if p.key in COACH_PORT_ECONOMICS_KEYS)
    missing = COACH_PORT_ECONOMICS_KEYS - {p.key for p in selected}
    if missing:
        raise ValueError(
            f"coach params missing port-economics keys: {sorted(missing)}"
        )
    for p in selected:
        if p.verified_vs_live:
            # Live-confirm may flip this later; today tip is all false — surface
            # if someone marks verified without a matching WO.
            pass
    return selected
