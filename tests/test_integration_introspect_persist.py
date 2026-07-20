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
