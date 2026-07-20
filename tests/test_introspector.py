"""TW-27 game-data introspector tests.

PROVENANCE CAVEAT: this repo has no live-captured StarDock/shipyard/
equipment screen yet -- the fixtures under `tests/fixtures/stardock_*
.txt` are CONSTRUCTED from the documented TW2002 shipyard/equipment-
shop table conventions, not a byte-for-byte real capture (same caveat
`state_parser.py`'s own CIM-report parsing carries -- see that
module's section docstring). Expect a refinement pass once the daemon
actually sees a real StarDock screen. `stardock_cargo_hold_quote*.txt`
(TW-27 P1-b) carry the identical caveat.
"""

import json
from pathlib import Path

import pytest

from twclient.game_data import load_game_data, validate_cargo_hold_row, validate_ship_row
from twclient.introspector import (
    parse_cargo_hold_price,
    parse_item_listing,
    parse_scanner_listing,
    parse_shipyard_listing,
    parse_transwarp_listing,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# -- parse_shipyard_listing ------------------------------------------------


def test_parse_shipyard_listing_clean_multi_ship_fixture():
    text = _load_fixture("stardock_shipyard_listing.txt")
    rows = parse_shipyard_listing(text)
    by_name = {r["ship_name"]: r for r in rows}
    assert set(by_name) == {
        "Fixture Scout",
        "Fixture Cruiser",
        "Fixture Frigate",
        "Fixture Transport",
    }

    scout = by_name["Fixture Scout"]
    assert scout["max_holds"] == 6
    assert scout["max_fighters"] == 500
    assert scout["max_shields"] == 100
    assert scout["combat_odds_modifier"] == pytest.approx(1.00)
    assert scout["turns_per_warp"] == 1
    assert scout["base_cost_credits"] == 95000
    assert scout["alignment_requirement"] == 0
    assert scout["rank_requirement"] is None
    assert scout["transwarp_capable"] is False
    assert scout["special_abilities"] == []
    assert scout["source"] == "introspected: stardock_shipyard"

    cruiser = by_name["Fixture Cruiser"]
    assert cruiser["alignment_requirement"] == -300
    assert cruiser["rank_requirement"] == "Alien"
    assert cruiser["transwarp_capable"] is True

    frigate = by_name["Fixture Frigate"]
    assert frigate["special_abilities"] == ["Cloak", "ECM"]
    assert frigate["alignment_requirement"] == -600


def test_parse_shipyard_listing_skips_malformed_row_without_crashing():
    """The fixture's narrative 'Not A Real Ship Row...' line and its own
    column-header line both carry no anchorable numeric columns -- both
    must be silently dropped, never turned into a garbage row, while the
    four well-formed sibling rows still parse."""
    text = _load_fixture("stardock_shipyard_listing.txt")
    rows = parse_shipyard_listing(text)
    assert len(rows) == 4
    assert all("Not A Real Ship Row" not in r["ship_name"] for r in rows)


def test_parse_shipyard_listing_no_listing_on_screen_returns_empty_list():
    assert parse_shipyard_listing("Command [TL=00753:0/0/0/850] (?=Help)? :") == []


def test_parse_shipyard_listing_anchors_to_latest_not_stale_scrollback():
    """Same discipline as `state_parser.parse_port_report`'s own
    regression test: a stale, already-closed listing sitting higher in
    the buffer must not shadow a genuinely fresher one printed after
    it."""
    text = (
        "-=-=-        StarDock Shipyard - Ship Registration        -=-=-\n"
        "Stale Ship  1 1 1 1.00 1 1  none  None  N\n"
        "-=-=-        End of Shipyard Listing        -=-=-\n"
        "(intervening scrolled game text)\n"
        "-=-=-        StarDock Shipyard - Ship Registration        -=-=-\n"
        "Fresh Ship  2 2 2 1.00 1 2  none  None  N\n"
        "-=-=-        End of Shipyard Listing        -=-=-\n"
    )
    rows = parse_shipyard_listing(text)
    assert [r["ship_name"] for r in rows] == ["Fresh Ship"]


def test_parse_shipyard_row_conforms_to_ship_row_schema():
    """Prove the parser's own output, plus a caller-supplied
    `last_verified_ts` (the persist layer's job -- see module
    docstring), fully satisfies `validate_ship_row`."""
    text = _load_fixture("stardock_shipyard_listing.txt")
    row = dict(parse_shipyard_listing(text)[0])
    row["last_verified_ts"] = "2026-07-19T00:00:00Z"
    validated = validate_ship_row(row)
    assert validated.source.startswith("introspected")


def test_parse_shipyard_listing_rows_load_via_game_data_loader(tmp_path):
    """End-to-end: introspector output, stamped with a timestamp the way
    the persist layer would, round-trips cleanly through
    `game_data.load_game_data`."""
    text = _load_fixture("stardock_shipyard_listing.txt")
    rows = parse_shipyard_listing(text)
    for row in rows:
        row["last_verified_ts"] = "2026-07-19T00:00:00Z"
    payload = {
        "world_id": "introspector-test",
        "ships": rows,
        "scanners": [],
        "transwarp": [],
        "items": [],
    }
    path = tmp_path / "introspected_game_data.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    data = load_game_data(path)
    assert len(data.ships) == 4
    assert all(s.source.startswith("introspected") for s in data.ships)


def test_non_introspected_source_is_rejected_by_validator():
    """Negative test: a row this parser could have produced, but with
    its source swapped to a non-introspected stock label, must be
    rejected -- proving `_require_introspected` (via `validate_ship_row`)
    enforces the introspected-only discipline rather than relying on
    this parser's own default `source=` never being wrong."""
    text = _load_fixture("stardock_shipyard_listing.txt")
    row = dict(parse_shipyard_listing(text)[0])
    row["last_verified_ts"] = "2026-07-19T00:00:00Z"
    row["source"] = "authored: some wiki stat table"
    with pytest.raises(ValueError, match="introspected"):
        validate_ship_row(row)


# -- parse_cargo_hold_price -------------------------------------------------


def test_parse_cargo_hold_price_clean_fixture():
    text = _load_fixture("stardock_cargo_hold_quote.txt")
    row = parse_cargo_hold_price(text)
    assert row == {"cost_per_hold": 1468, "source": "introspected: stardock_cargo_holds"}


def test_parse_cargo_hold_price_at_max_holds_returns_none():
    """The block is present and closed, but there's no price line to
    show (ship already at max holds) -- absence, never a guess."""
    text = _load_fixture("stardock_cargo_hold_quote_at_max.txt")
    assert parse_cargo_hold_price(text) is None


def test_parse_cargo_hold_price_no_block_on_screen_returns_none():
    assert parse_cargo_hold_price("Command [TL=00753:0/0/0/850] (?=Help)? :") is None


def test_parse_cargo_hold_price_anchors_to_latest_not_stale_scrollback():
    """Same stale-scrollback discipline as `parse_shipyard_listing`'s
    own regression test: an older, already-closed quote sitting higher
    in the buffer must not shadow a genuinely fresher one."""
    text = (
        "-=-=-        StarDock Shipyard - Cargo Hold Upgrade        -=-=-\n"
        "Holds cost 1,000 credits each.\n"
        "-=-=-        End of Cargo Hold Upgrade Quote        -=-=-\n"
        "(intervening scrolled game text)\n"
        "-=-=-        StarDock Shipyard - Cargo Hold Upgrade        -=-=-\n"
        "Holds cost 2,500 credits each.\n"
        "-=-=-        End of Cargo Hold Upgrade Quote        -=-=-\n"
    )
    assert parse_cargo_hold_price(text)["cost_per_hold"] == 2500


def test_parse_cargo_hold_price_row_conforms_to_cargo_hold_row_schema():
    text = _load_fixture("stardock_cargo_hold_quote.txt")
    row = dict(parse_cargo_hold_price(text))
    row["last_verified_ts"] = "2026-07-19T00:00:00Z"
    validated = validate_cargo_hold_row(row)
    assert validated.cost_per_hold == 1468
    assert validated.source.startswith("introspected")


def test_parse_cargo_hold_price_rows_load_via_game_data_loader(tmp_path):
    text = _load_fixture("stardock_cargo_hold_quote.txt")
    row = parse_cargo_hold_price(text)
    row["last_verified_ts"] = "2026-07-19T00:00:00Z"
    payload = {
        "world_id": "introspector-test",
        "ships": [],
        "scanners": [],
        "transwarp": [],
        "items": [],
        "cargo_holds": [row],
    }
    path = tmp_path / "introspected_game_data.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    data = load_game_data(path)
    assert len(data.cargo_holds) == 1
    assert data.cargo_holds[0].cost_per_hold == 1468
    assert data.cargo_holds[0].source.startswith("introspected")


def test_cargo_hold_non_introspected_source_is_rejected_by_validator():
    text = _load_fixture("stardock_cargo_hold_quote.txt")
    row = dict(parse_cargo_hold_price(text))
    row["last_verified_ts"] = "2026-07-19T00:00:00Z"
    row["source"] = "authored: some wiki stat table"
    with pytest.raises(ValueError, match="introspected"):
        validate_cargo_hold_row(row)


# -- parse_scanner_listing / parse_transwarp_listing / parse_item_listing --


def test_parse_scanner_listing():
    text = _load_fixture("stardock_equipment_listing.txt")
    rows = parse_scanner_listing(text)
    by_name = {r["scanner_type"]: r for r in rows}
    assert set(by_name) == {"Fixture Density Scanner", "Fixture Holo Scanner"}

    density = by_name["Fixture Density Scanner"]
    assert density["cost_credits"] == 50000
    assert density["capability_notes"] == "Reveals adjacent sector signatures"
    assert density["source"].startswith("introspected")


def test_parse_scanner_listing_no_listing_on_screen_returns_empty_list():
    assert parse_scanner_listing("Command [TL=00753:0/0/0/850] (?=Help)? :") == []


def test_parse_transwarp_listing():
    text = _load_fixture("stardock_equipment_listing.txt")
    rows = parse_transwarp_listing(text)
    assert len(rows) == 1
    assert rows[0]["cost_credits"] == 4750000
    assert "previously visited" in rows[0]["range_notes"]
    assert rows[0]["source"].startswith("introspected")
    assert "name" not in rows[0]  # TranswarpRow has no name field -- discarded


def test_parse_item_listing():
    text = _load_fixture("stardock_equipment_listing.txt")
    rows = parse_item_listing(text)
    by_name = {r["item_name"]: r for r in rows}
    assert set(by_name) == {"Fixture Genesis Torpedo", "Fixture Space Mine"}

    genesis = by_name["Fixture Genesis Torpedo"]
    assert genesis["cost_credits"] == 250000
    assert "new planet" in genesis["effect_notes"]
    assert genesis["source"].startswith("introspected")


def test_parse_item_listing_skips_malformed_row_without_crashing():
    text = _load_fixture("stardock_equipment_listing.txt")
    rows = parse_item_listing(text)
    assert len(rows) == 2
    assert all("Not A Real Item Row" not in r["item_name"] for r in rows)
