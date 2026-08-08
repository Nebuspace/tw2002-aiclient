"""Unit pins for density_scan.parse_density_scan (synthetic fixtures)."""

from __future__ import annotations

from tw2002_aiclient.density_scan import DENSITY_VALUE_TABLE, parse_density_scan


def test_value_table_matches_canon_atoms() -> None:
    assert DENSITY_VALUE_TABLE == {
        1: "beacon",
        5: "fighter",
        10: "mine",
        40: "ship",
        100: "port",
        500: "planet",
    }


def test_parse_colon_and_arrow_row_shapes() -> None:
    text = (
        "Sector  1234  Density:  105\n"
        "Sector: 5678 Density = 500\n"
        "Sector 999 ==> Density 0\n"
    )
    assert parse_density_scan(text) == {1234: 105, 5678: 500, 999: 0}


def test_last_match_wins_per_sector() -> None:
    text = "Sector 10 Density: 5\nSector 10 Density: 40\n"
    assert parse_density_scan(text) == {10: 40}


def test_junk_and_non_string_fail_closed() -> None:
    assert parse_density_scan(None) == {}
    assert parse_density_scan("") == {}
    assert parse_density_scan("Density Scanner for sale 50,000") == {}
    assert parse_density_scan("Sector abc Density: 5") == {}


def test_decode_helpers_fail_closed_on_junk() -> None:
    from tw2002_aiclient.density_scan import (
        decode_density_atoms,
        fighter_presence_hypothesis,
    )

    assert decode_density_atoms(None) == []
    assert fighter_presence_hypothesis(None) is None
