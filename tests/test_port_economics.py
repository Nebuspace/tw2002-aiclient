"""PWO-100 — hypothesis-tagged port-economics params."""

from __future__ import annotations

from pathlib import Path

import pytest

from tw2002_aiclient import port_economics, trade_adapter
from tw2002_aiclient.coach_kb import DEFAULT_DATA_DIR


def test_authored_params_carry_hypothesis_tag() -> None:
    port_economics.assert_all_unverified_tagged()
    for p in port_economics.all_hypothesis_params():
        assert p.tag == "hypothesis"
        assert p.verified_vs_live is False
        assert p.source_note.strip()


def test_floor_prices_match_canon_ordering_and_values() -> None:
    floors = port_economics.hypothesized_floor_prices()
    assert floors == {"Fuel Ore": 20.0, "Organics": 30.0, "Equipment": 40.0}
    assert floors["Equipment"] > floors["Organics"] > floors["Fuel Ore"]


def test_trade_adapter_reexports_port_economics_floors() -> None:
    """No silent hardcoded product stats left as the adapter's own literals."""
    assert dict(trade_adapter.DEFAULT_FLOOR_PRICES) == (
        port_economics.hypothesized_floor_prices()
    )
    assert trade_adapter.DEFAULT_CEILING_MULTIPLIER == (
        port_economics.hypothesized_ceiling_multiplier()
    )
    assert trade_adapter.DEFAULT_BUY_SELL_SPREAD_OF_FLOOR == (
        port_economics.hypothesized_buy_sell_spread_of_floor()
    )


def test_trade_adapter_source_has_no_silent_floor_literal() -> None:
    """Guard: floor map must not be re-inlined in trade_adapter.py."""
    src = Path(trade_adapter.__file__).read_text(encoding="utf-8")
    assert '"Fuel Ore": 20.0' not in src
    assert "hypothesized_floor_prices" in src


def test_coach_port_economics_params_require_verified_flag() -> None:
    rows = port_economics.load_coach_port_economics_params()
    keys = {p.key for p in rows}
    assert keys == port_economics.COACH_PORT_ECONOMICS_KEYS
    for p in rows:
        assert p.verified_vs_live is False
        assert p.source_note.strip()


def test_coach_port_economics_missing_key_raises(tmp_path: Path) -> None:
    # Minimal strategies stub + incomplete params
    strategies = DEFAULT_DATA_DIR / "strategies.json"
    params = tmp_path / "params.json"
    params.write_text(
        '{"version": 1, "params": ['
        '{"key": "port_regrowth_pct_per_day", "value": 10, "unit": "percent",'
        ' "verified_vs_live": false, "source_note": "x"}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing port-economics keys"):
        port_economics.load_coach_port_economics_params(params)
    # silence unused — strategies must exist on tip
    assert strategies.is_file()
