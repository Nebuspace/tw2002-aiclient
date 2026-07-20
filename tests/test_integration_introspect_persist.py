"""TW-26/27 introspector-to-persist chain integration test.

The two lanes (introspector parsing, game_data persist/query) were built
in disjoint worktrees against each other's documented contract, never
against each other's actual code. This is the one test that imports
both real modules together and proves the seam actually holds: a row
`introspector.parse_shipyard_listing` emits from a real fixture is
accepted as-is by `game_data.persist_ship_row` (including the
write-time `last_verified_ts` stamp the introspector deliberately omits
-- see `game_data.persist_ship_row`'s docstring) and round-trips back
out through `game_data.get_ship` unchanged.
"""

from pathlib import Path

from twclient import game_data, introspector

FIXTURES = Path(__file__).parent / "fixtures"
WORLD_ID = "hostIntegration__F__CHAIN"


def test_shipyard_listing_parses_and_persists_end_to_end(tmp_path):
    text = (FIXTURES / "stardock_shipyard_listing.txt").read_text(encoding="utf-8")
    rows = introspector.parse_shipyard_listing(text)
    assert rows

    row = rows[0]
    assert "last_verified_ts" not in row  # introspector's documented no-clock contract

    persisted = game_data.persist_ship_row(WORLD_ID, row, state_dir=tmp_path)
    assert isinstance(persisted, game_data.ShipRow)
    assert persisted.ship_name == row["ship_name"]
    assert persisted.last_verified_ts  # write-time stamp landed

    fetched = game_data.get_ship(WORLD_ID, row["ship_name"], state_dir=tmp_path)
    assert fetched == persisted


def test_cargo_hold_price_parses_and_persists_end_to_end(tmp_path):
    """TW-27 P1-b's seam: `introspector.parse_cargo_hold_price`'s output
    is accepted as-is by `game_data.persist_cargo_hold_price` and
    round-trips back out through `game_data.get_cargo_hold_price`."""
    text = (FIXTURES / "stardock_cargo_hold_quote.txt").read_text(encoding="utf-8")
    row = introspector.parse_cargo_hold_price(text)
    assert row is not None
    assert "last_verified_ts" not in row  # introspector's documented no-clock contract

    persisted = game_data.persist_cargo_hold_price(WORLD_ID, row, state_dir=tmp_path)
    assert isinstance(persisted, game_data.CargoHoldRow)
    assert persisted.cost_per_hold == row["cost_per_hold"]
    assert persisted.last_verified_ts  # write-time stamp landed

    fetched = game_data.get_cargo_hold_price(WORLD_ID, state_dir=tmp_path)
    assert fetched == persisted


def test_cargo_hold_price_absent_screen_persists_nothing(tmp_path):
    """The ABSENCE half of the same seam: a StarDock screen with no
    parseable price (ship already at max holds) must leave the store
    untouched -- never a guessed/zero price for the autopilot scheduler
    to act on."""
    text = (FIXTURES / "stardock_cargo_hold_quote_at_max.txt").read_text(encoding="utf-8")
    assert introspector.parse_cargo_hold_price(text) is None
    assert game_data.get_cargo_hold_price(WORLD_ID, state_dir=tmp_path) is None
